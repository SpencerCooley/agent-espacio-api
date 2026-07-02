"""
Settings controller.

Handles global instance settings stored in the settings table.
"""
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError

from models.settings import Setting


def get_setting(db: Session, key: str) -> Optional[Any]:
    """
    Get a setting value by key.
    
    Args:
        db: Database session
        key: Setting key
        
    Returns:
        The setting value or None if not found.
    """
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            return setting.value
    except ProgrammingError:
        # Table may not exist yet (migration not applied)
        pass
    return None


def get_all_settings(db: Session) -> Dict[str, Any]:
    """
    Get all settings as a dictionary.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary of all settings.
    """
    try:
        settings = db.query(Setting).all()
        return {s.key: s.value for s in settings}
    except ProgrammingError:
        # Table may not exist yet (migration not applied)
        return {}


def get_public_theme(db: Session) -> Dict[str, str]:
    """
    Get the public theme setting.

    Returns:
    { theme_id: str, mode: 'light' | 'dark' }
    """
    value = get_setting(db, 'public_theme')
    if value and isinstance(value, dict):
        return {
            'theme_id': value.get('theme_id', ''),
            'mode': value.get('mode', 'dark'),
        }
    return {
        'theme_id': '',
        'mode': 'dark',
    }


def set_setting(db: Session, key: str, value: Any) -> Setting:
    """
    Set a setting value. Creates or updates.
    
    Args:
        db: Database session
        key: Setting key
        value: Setting value (must be JSON-serializable)
        
    Returns:
        The updated Setting object.
    """
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)
    
    db.commit()
    db.refresh(setting)
    return setting


def set_public_theme(db: Session, theme_id: str, mode: str) -> Setting:
    """
    Set the public theme.

    Args:
        db: Database session
        theme_id: Theme UUID
        mode: 'light' or 'dark'

    Returns:
        The updated Setting object.
    """
    return set_setting(db, 'public_theme', {
        'theme_id': theme_id,
        'mode': mode,
    })


def get_branding(db: Session) -> Dict[str, Any]:
    """
    Get the branding settings.

    Returns:
        {
            logo_light_asset_id: str|None,
            logo_dark_asset_id: str|None,
            background_asset_id: str|None,
            background_style: 'cover'|'tile'
        }
    """
    value = get_setting(db, 'branding')
    if value and isinstance(value, dict):
        return {
            'logo_light_asset_id': value.get('logo_light_asset_id') or None,
            'logo_dark_asset_id': value.get('logo_dark_asset_id') or None,
            'background_asset_id': value.get('background_asset_id') or None,
            'background_style': value.get('background_style', 'cover'),
        }
    return {
        'logo_light_asset_id': None,
        'logo_dark_asset_id': None,
        'background_asset_id': None,
        'background_style': 'cover',
    }


def set_branding(db: Session,
                 logo_light_asset_id: Optional[str] = None,
                 logo_dark_asset_id: Optional[str] = None,
                 background_asset_id: Optional[str] = None,
                 background_style: str = 'cover') -> Setting:
    """
    Set the branding settings.

    Args:
        db: Database session
        logo_light_asset_id: Asset UUID for the light mode logo, or None to clear
        logo_dark_asset_id: Asset UUID for the dark mode logo, or None to clear
        background_asset_id: Asset UUID for the background, or None to clear
        background_style: 'cover' or 'tile'

    Returns:
        The updated Setting object.
    """
    return set_setting(db, 'branding', {
        'logo_light_asset_id': logo_light_asset_id,
        'logo_dark_asset_id': logo_dark_asset_id,
        'background_asset_id': background_asset_id,
        'background_style': background_style,
    })
