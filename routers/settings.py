"""
Settings router.

Global instance settings API.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from dependencies.dependencies import get_db, require_auth
from controllers.settings import get_all_settings, get_public_theme, set_public_theme, get_branding, set_branding
from controllers.asset.signed_url import generate_signed_url
from uuid import UUID

router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
)


class PublicThemeUpdate(BaseModel):
    theme_id: str
    mode: str


@router.get("")
async def get_settings(
    db: Session = Depends(get_db)
):
    """
    Get all global settings.

    No authentication required for reading public_theme (needed by public pages).
    """
    settings = get_all_settings(db)

    # Ensure public_theme always has a default shape
    if 'public_theme' not in settings:
        settings['public_theme'] = {
            'theme_id': '',
            'mode': 'dark',
        }

    return {"settings": settings}


@router.get("/public-theme")
async def get_public_theme_endpoint(
    db: Session = Depends(get_db)
):
    """
    Get the public theme.

    No authentication required.
    """
    theme = get_public_theme(db)
    return theme


@router.put("/public-theme")
async def update_public_theme(
    data: PublicThemeUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_auth)
):
    """
    Update the public theme.

    Any authenticated user can update this.
    """
    if data.mode not in ('light', 'dark'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mode must be 'light' or 'dark'"
        )

    setting = set_public_theme(db, data.theme_id, data.mode)
    return {"public_theme": setting.value}


class BrandingUpdate(BaseModel):
    logo_light_asset_id: Optional[str] = None
    logo_dark_asset_id: Optional[str] = None
    background_asset_id: Optional[str] = None
    background_style: str = "cover"


@router.get("/branding")
async def get_branding_endpoint(
    db: Session = Depends(get_db)
):
    """
    Get the branding settings with signed URLs for public access.

    No authentication required.
    """
    branding = get_branding(db)

    # Generate signed URLs for branding assets so public pages can display them
    # without requiring authentication
    def _signed_url(asset_id: str | None, size: int = None) -> str | None:
        if not asset_id:
            return None
        try:
            return generate_signed_url(UUID(asset_id), size=size, expiry_seconds=3600)
        except Exception:
            return None

    branding['logo_light_url'] = _signed_url(branding.get('logo_light_asset_id'), size=256)
    branding['logo_dark_url'] = _signed_url(branding.get('logo_dark_asset_id'), size=256)
    branding['background_url'] = _signed_url(branding.get('background_asset_id'), size=512)

    return branding


@router.put("/branding")
async def update_branding(
    data: BrandingUpdate,
    db: Session = Depends(get_db),
    user = Depends(require_auth)
):
    """
    Update the branding settings.

    Any authenticated user can update this.
    """
    if data.background_style not in ('cover', 'tile'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="background_style must be 'cover' or 'tile'"
        )

    setting = set_branding(
        db,
        logo_light_asset_id=data.logo_light_asset_id,
        logo_dark_asset_id=data.logo_dark_asset_id,
        background_asset_id=data.background_asset_id,
        background_style=data.background_style,
    )
    return {"branding": setting.value}
