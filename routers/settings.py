"""
Settings router.

Global instance settings API.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from dependencies.dependencies import get_db, require_auth
from controllers.settings import get_all_settings, get_public_theme, set_public_theme

router = APIRouter(
    prefix="/settings",
    tags=["Settings"],
)


class PublicThemeUpdate(BaseModel):
    name: str
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
    
    # Ensure public_theme always has a default
    if 'public_theme' not in settings:
        settings['public_theme'] = {
            'name': 'hackerBuzz',
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
    
    setting = set_public_theme(db, data.name, data.mode)
    return {"public_theme": setting.value}
