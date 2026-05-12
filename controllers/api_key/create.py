"""
API key controller - create API key.
"""
from typing import Tuple

from sqlalchemy.orm import Session

from models.api_key import APIKey
from utils.token import generate_api_key
from utils.api_key import hash_api_key, get_api_key_prefix


def create_api_key(db: Session, name: str) -> Tuple[APIKey, str]:
    """
    Create a new API key for agent authentication.
    
    The full key is shown only once on creation. Only the hash is stored.
    
    Args:
        db: Database session
        name: Human-readable name for the key
        
    Returns:
        Tuple of (APIKey object, plain API key string)
        
    Example:
        >>> api_key, plain_key = create_api_key(db, "laptop-main")
        >>> print(plain_key)  # agent-esp-a3f7b2d8...
        >>> # Store plain_key securely - it won't be shown again!
    """
    # Generate the API key
    plain_key = generate_api_key()
    
    # Hash for storage
    key_hash = hash_api_key(plain_key)
    
    # Get prefix for display
    prefix = get_api_key_prefix(plain_key)
    
    # Create database record
    api_key = APIKey(
        name=name,
        key_hash=key_hash,
        prefix=prefix,
        is_active=True
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return api_key, plain_key
