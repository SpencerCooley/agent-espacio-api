"""
API key controller - validate API key.
"""
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session

from models.api_key import APIKey
from utils.api_key import hash_api_key


def validate_api_key(db: Session, plain_key: str) -> Optional[APIKey]:
    """
    Validate an API key by checking its hash against stored hashes.
    
    Also updates the last_used_at timestamp on successful validation.
    
    Args:
        db: Database session
        plain_key: Plain text API key (e.g., 'agent-esp-...')
        
    Returns:
        APIKey object if valid and active, None otherwise
    """
    # Hash the provided key
    key_hash = hash_api_key(plain_key)
    
    # Find matching key
    api_key = db.query(APIKey).filter(
        APIKey.key_hash == key_hash,
        APIKey.is_active == True
    ).first()
    
    if not api_key:
        return None
    
    # Update last used timestamp
    api_key.last_used_at = datetime.utcnow()
    db.commit()
    
    return api_key
