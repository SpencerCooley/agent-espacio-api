"""
Themes controller.

Handles theme CRUD operations stored in the themes table.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError

from models.theme import Theme


def get_all_themes(db: Session) -> List[Theme]:
    """
    Get all themes.

    Returns lightweight list for dropdowns.
    """
    try:
        return db.query(Theme).all()
    except ProgrammingError:
        return []


def get_theme_by_id(db: Session, theme_id: str) -> Optional[Theme]:
    """
    Get a theme by its UUID.

    Returns the full theme with light_definition and dark_definition.
    """
    try:
        return db.query(Theme).filter(Theme.id == theme_id).first()
    except ProgrammingError:
        return None


def get_public_theme_definition(db: Session, theme_id: str, mode: str) -> Optional[Dict[str, Any]]:
    """
    Get the resolved theme definition for a given mode.

    Args:
        db: Database session
        theme_id: Theme UUID
        mode: 'light' or 'dark'

    Returns:
        The theme definition dict or None if theme not found.
    """
    theme = get_theme_by_id(db, theme_id)
    if not theme:
        return None
    if mode == 'light':
        return theme.light_definition
    return theme.dark_definition


def create_theme(db: Session, name: str, light_definition: dict, dark_definition: dict) -> Theme:
    """
    Create a new theme.

    Args:
        db: Database session
        name: Theme display name
        light_definition: MUI ThemeOptions for light mode
        dark_definition: MUI ThemeOptions for dark mode

    Returns:
        The created Theme object.
    """
    theme = Theme(
        name=name,
        light_definition=light_definition,
        dark_definition=dark_definition,
    )
    db.add(theme)
    db.commit()
    db.refresh(theme)
    return theme


def update_theme(db: Session, theme_id: str, name: Optional[str] = None,
                 light_definition: Optional[dict] = None,
                 dark_definition: Optional[dict] = None) -> Optional[Theme]:
    """
    Update an existing theme.

    Args:
        db: Database session
        theme_id: Theme UUID
        name: Optional new display name
        light_definition: Optional new light mode definition
        dark_definition: Optional new dark mode definition

    Returns:
        The updated Theme object, or None if not found.
    """
    theme = get_theme_by_id(db, theme_id)
    if not theme:
        return None

    if name is not None:
        theme.name = name
    if light_definition is not None:
        theme.light_definition = light_definition
    if dark_definition is not None:
        theme.dark_definition = dark_definition

    db.commit()
    db.refresh(theme)
    return theme


def delete_theme(db: Session, theme_id: str) -> bool:
    """
    Delete a theme.

    Args:
        db: Database session
        theme_id: Theme UUID

    Returns:
        True if deleted, False if not found.
    """
    theme = get_theme_by_id(db, theme_id)
    if not theme:
        return False

    db.delete(theme)
    db.commit()
    return True
