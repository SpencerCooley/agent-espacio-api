"""
Profile get controller.

Handles retrieving profiles.
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from models import Profile, User
from models.artifact import Artifact


def get_or_create_profile(db: Session, user_id: int) -> Profile:
    """
    Get a user's profile, creating an empty one if it doesn't exist.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Profile object (existing or newly created)
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        # Create empty profile
        profile = Profile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def get_public_profile(db: Session, user_id: int) -> Profile:
    """
    Get a user's public profile.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Profile object
        
    Raises:
        HTTPException: If profile not found
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return profile


def get_authored_public_compositions(db: Session, user_id: int, limit: int = 6, offset: int = 0) -> tuple[list[Artifact], int]:
    """
    Get all public composer artifacts where this user is marked as the author.
    
    Uses JSONB query on content->>'author_id' matching the user_id as string.
    Compositions must be public (is_public=True OR in a public folder).
    Ordered by published_at descending (most recent first).
    
    Args:
        db: Database session
        user_id: User ID
        limit: Max items to return (default 6)
        offset: Pagination offset
        
    Returns:
        Tuple of (list of public composer artifacts, total count)
    """
    from controllers.public import is_artifact_public
    
    user_id_str = str(user_id)
    
    # Get all composers that reference this author
    candidates = (
        db.query(Artifact)
        .filter(
            Artifact.type == "composer",
            Artifact.content['author_id'].astext == user_id_str,
        )
        .all()
    )
    
    # Filter by public access and sort by published_at descending
    public_artifacts = []
    for a in candidates:
        if is_artifact_public(db, a):
            content = a.content or {}
            published_at = content.get("published_at")
            if not published_at:
                published_at = a.created_at.isoformat() if a.created_at else ""
            public_artifacts.append((a, published_at))
    
    # Sort by published_at descending (most recent first)
    public_artifacts.sort(key=lambda x: x[1], reverse=True)
    
    total = len(public_artifacts)
    
    # Apply pagination
    paginated = [a for a, _ in public_artifacts[offset:offset + limit]]
    
    return paginated, total


def list_public_authors(db: Session, limit: int = 50) -> list[dict]:
    """
    List all users who are marked as authors on at least one public composition.
    
    Only includes profiles with a display_name set.
    Sorted by most recent composition.
    
    Args:
        db: Database session
        limit: Max number of authors
        
    Returns:
        List of dicts: {user_id, display_name, bio, avatar_user_id, composition_count, latest_published_at}
    """
    from controllers.public import is_artifact_public
    
    # Get all composers with author_id set
    composers = (
        db.query(Artifact)
        .filter(
            Artifact.type == "composer",
            Artifact.content['author_id'].astext.isnot(None),
        )
        .order_by(desc(Artifact.updated_at))
        .all()
    )
    
    # Filter public and group by author
    author_map: dict[int, dict] = {}
    for artifact in composers:
        if not is_artifact_public(db, artifact):
            continue
        
        author_id_str = (artifact.content or {}).get("author_id")
        if not author_id_str:
            continue
        
        try:
            author_id = int(author_id_str)
        except (ValueError, TypeError):
            continue
        
        entry = author_map.get(author_id)
        if not entry:
            entry = {
                "user_id": author_id,
                "composition_count": 0,
                "latest_published_at": None,
            }
            author_map[author_id] = entry
        
        entry["composition_count"] += 1
        published_at = artifact.content.get("published_at") or artifact.updated_at.isoformat()
        if entry["latest_published_at"] is None or published_at > entry["latest_published_at"]:
            entry["latest_published_at"] = published_at
    
    # Fetch profiles for authors and filter to those with display_name
    result = []
    for author_id, entry in author_map.items():
        profile = db.query(Profile).filter(Profile.user_id == author_id).first()
        if not profile or not profile.display_name:
            continue
        
        result.append({
            "user_id": author_id,
            "display_name": profile.display_name,
            "bio": profile.bio,
            "avatar_user_id": profile.avatar_user_id,
            "composition_count": entry["composition_count"],
            "latest_published_at": entry["latest_published_at"],
        })
    
    # Sort by latest published date desc
    result.sort(key=lambda x: x["latest_published_at"] or "", reverse=True)
    return result[:limit]
