"""
Themes router.

Public API for listing and retrieving themes.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from dependencies.dependencies import get_db, require_auth
from controllers.themes import get_all_themes, get_theme_by_id, create_theme, update_theme, delete_theme

router = APIRouter(
    prefix="/themes",
    tags=["Themes"],
)


class ThemeListItem(BaseModel):
    id: str
    name: str


class ThemeDefinitionResponse(BaseModel):
    id: str
    name: str
    light_definition: dict
    dark_definition: dict


class CreateThemeRequest(BaseModel):
    name: str
    light_definition: dict
    dark_definition: dict


class UpdateThemeRequest(BaseModel):
    name: Optional[str] = None
    light_definition: Optional[dict] = None
    dark_definition: Optional[dict] = None


@router.get("")
async def list_themes(
    db: Session = Depends(get_db)
):
    """
    List all available themes.

    No authentication required.
    """
    themes = get_all_themes(db)
    return {
        "themes": [
            ThemeListItem(id=str(t.id), name=t.name)
            for t in themes
        ]
    }


@router.get("/{theme_id}")
async def get_theme(
    theme_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a single theme with full definitions.

    No authentication required.
    """
    theme = get_theme_by_id(db, theme_id)
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Theme not found"
        )
    return ThemeDefinitionResponse(
        id=str(theme.id),
        name=theme.name,
        light_definition=theme.light_definition,
        dark_definition=theme.dark_definition,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_new_theme(
    data: CreateThemeRequest,
    db: Session = Depends(get_db),
    user = Depends(require_auth)
):
    """
    Create a new theme.

    Requires authentication.
    """
    theme = create_theme(
        db,
        name=data.name,
        light_definition=data.light_definition,
        dark_definition=data.dark_definition,
    )
    return ThemeDefinitionResponse(
        id=str(theme.id),
        name=theme.name,
        light_definition=theme.light_definition,
        dark_definition=theme.dark_definition,
    )


@router.put("/{theme_id}")
async def update_existing_theme(
    theme_id: str,
    data: UpdateThemeRequest,
    db: Session = Depends(get_db),
    user = Depends(require_auth)
):
    """
    Update an existing theme.

    Requires authentication.
    """
    theme = update_theme(
        db,
        theme_id=theme_id,
        name=data.name,
        light_definition=data.light_definition,
        dark_definition=data.dark_definition,
    )
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Theme not found"
        )
    return ThemeDefinitionResponse(
        id=str(theme.id),
        name=theme.name,
        light_definition=theme.light_definition,
        dark_definition=theme.dark_definition,
    )


@router.delete("/{theme_id}")
async def delete_existing_theme(
    theme_id: str,
    db: Session = Depends(get_db),
    user = Depends(require_auth)
):
    """
    Delete a theme.

    Requires authentication.
    """
    deleted = delete_theme(db, theme_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Theme not found"
        )
    return {"message": "Theme deleted successfully"}
