"""
API key controller - create API key.
"""
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from models.api_key import APIKey
from models.user import User
from utils.token import generate_api_key
from utils.api_key import hash_api_key, get_api_key_prefix
from utils.crypto import encrypt_api_key


def create_api_key(
    db: Session,
    name: str,
    user_id: Optional[int] = None,
) -> Tuple[APIKey, str]:
    """
    Create a new API key for agent authentication.

    Stores the SHA-256 hash (for auth lookup) plus the Fernet-encrypted full
    key (so admins and the assigned user can retrieve it later).

    Optional user_id assigns the key's permission source (inherits that user's
    folder grants). None = global unrestricted key.

    Args:
        db: Database session
        name: Human-readable name for the key
        user_id: Optional user whose grants the key inherits

    Returns:
        Tuple of (APIKey object, plain API key string)

    Raises:
        ValueError: If user_id is set but user does not exist
        RuntimeError: If SECRET_KEY is not configured
    """
    if user_id is not None:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found for API key assignment")

    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)
    key_encrypted = encrypt_api_key(plain_key)
    prefix = get_api_key_prefix(plain_key)

    api_key = APIKey(
        name=name,
        key_hash=key_hash,
        key_encrypted=key_encrypted,
        prefix=prefix,
        is_active=True,
        user_id=user_id,
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    return api_key, plain_key
