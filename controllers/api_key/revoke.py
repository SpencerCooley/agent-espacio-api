"""
API key controller - revoke API key.
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.api_key import APIKey


def revoke_api_key(db: Session, key_id: int) -> Optional[APIKey]:
    """
    Revoke (soft delete) an API key.
    
    Args:
        db: Database session
        key_id: API key ID to revoke
        
    Returns:
        Revoked APIKey object if found, None otherwise
    """
    api_key = db.query(APIKey).filter(APIKey.id == key_id).first()
    
    if not api_key:
        return None
    
    # Soft delete
    api_key.is_active = False
    db.commit()
    db.refresh(api_key)
    
    return api_key


def activate_api_key(db: Session, key_id: int) -> Optional[APIKey]:
    """
    Reactivate a previously revoked API key.
    
    Args:
        db: Database session
        key_id: API key ID to activate
        
    Returns:
        Activated APIKey object if found, None otherwise
    """
    api_key = db.query(APIKey).filter(APIKey.id == key_id).first()
    
    if not api_key:
        return None
    
    api_key.is_active = True
    db.commit()
    db.refresh(api_key)
    
    return api_key
