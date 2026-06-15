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
        { name: str, mode: 'light' | 'dark' }
        Defaults to hackerBuzz dark if not set.
    """
    value = get_setting(db, 'public_theme')
    if value and isinstance(value, dict):
        return {
            'name': value.get('name', 'hackerBuzz'),
            'mode': value.get('mode', 'dark'),
        }
    return {
        'name': 'hackerBuzz',
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


def set_public_theme(db: Session, name: str, mode: str) -> Setting:
    """
    Set the public theme.
    
    Args:
        db: Database session
        name: Theme name (e.g., 'hackerBuzz')
        mode: 'light' or 'dark'
        
    Returns:
        The updated Setting object.
    """
    return set_setting(db, 'public_theme', {
        'name': name,
        'mode': mode,
    })
