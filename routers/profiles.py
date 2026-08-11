"""
Profile router.

Endpoints for profile management and avatar upload.
"""
import os

from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db, require_auth
from models import User
from models.profile import Profile
from controllers import profile as profile_controller
from controllers.profile.avatar import get_avatar_url, _get_avatar_path, AVATARS_DIR
from types_definitions.profile import (
    ProfileResponse,
    ProfileUpdateRequest,
    PublicProfileResponse,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


class ProfileSearchResult(PublicProfileResponse):
    """Profile search result with email."""
    email: str


def _profile_to_response(profile, db) -> ProfileResponse:
    """Convert profile model to response with avatar URL."""
    avatar_url = None
    if profile.avatar_user_id:
        avatar_url = get_avatar_url(profile.avatar_user_id, size=256)
    
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        display_name=profile.display_name,
        bio=profile.bio,
        avatar_url=avatar_url,
        avatar_asset_id=str(profile.avatar_user_id) if profile.avatar_user_id else None,
    )


# AVATAR ENDPOINTS MUST COME BEFORE /{user_id} ROUTE

@router.get("/avatar/{user_id}/{size}")
def serve_avatar(
    user_id: int,
    size: int,
):
    """
    Serve an avatar image file.
    
    Sizes: 128, 256, 512
    """
    # Validate size
    if size not in (128, 256, 512):
        size = 256
    
    path = _get_avatar_path(user_id, size)
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Avatar not found")
    
    return FileResponse(
        path,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400"}  # Cache for 24 hours
    )


@router.get("/avatar/{user_id}")
def serve_avatar_default(
    user_id: int,
):
    """Serve default size (256) avatar."""
    return serve_avatar(user_id, 256)


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Get current user's profile (creates empty one if missing)."""
    profile = profile_controller.get_or_create_profile(db, current_user.id)
    return _profile_to_response(profile, db)


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    data: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Update current user's profile."""
    profile = profile_controller.get_or_create_profile(db, current_user.id)
    updated = profile_controller.update_profile(db, profile, data)
    return _profile_to_response(updated, db)


@router.post("/me/avatar", response_model=ProfileResponse)
def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Upload avatar for current user."""
    updated = profile_controller.upload_avatar(db, current_user, file)
    return _profile_to_response(updated, db)


@router.get("/search", response_model=List[ProfileSearchResult])
def search_profiles(
    q: str = Query(..., min_length=2, description="Search query for display_name or email"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Search profiles by display_name or email.
    
    Used for author selection autocomplete in composer editor.
    """
    query = q.lower()
    
    results = (
        db.query(Profile, User)
        .join(User, Profile.user_id == User.id)
        .filter(
            or_(
                func.lower(Profile.display_name).ilike(f"%{query}%"),
                func.lower(User.email).ilike(f"%{query}%")
            )
        )
        .limit(limit)
        .all()
    )
    
    return [
        ProfileSearchResult(
            user_id=profile.user_id,
            display_name=profile.display_name,
            avatar_url=get_avatar_url(profile.avatar_user_id, size=128) if profile.avatar_user_id else None,
            email=user.email,
        )
        for profile, user in results
    ]


@router.get("/{user_id}", response_model=PublicProfileResponse)
def get_public_profile(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Get a user's public profile (for author display)."""
    profile = profile_controller.get_public_profile(db, user_id)
    
    avatar_url = None
    if profile.avatar_user_id:
        avatar_url = get_avatar_url(profile.avatar_user_id, size=128)
    
    return PublicProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        avatar_url=avatar_url,
    )
