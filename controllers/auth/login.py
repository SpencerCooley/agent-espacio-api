"""
Authentication controller - login.
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from models.user import User
from models.token import Token
from utils.password import verify_password
from utils.token import generate_token_string


def login(db: Session, email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate user with email and password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        
    Returns:
        dict with token, expires_at, and user object if successful, None otherwise
    """
    # Find user by email
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        return None
    
    # Verify password
    if not verify_password(password, user.hashed_password):
        return None
    
    # Generate new token
    token_string = generate_token_string()
    expires_at = Token.calculate_expiration()
    
    # Create token record
    token = Token(
        token=token_string,
        expires_at=expires_at,
        user_id=user.id
    )
    
    db.add(token)
    db.commit()
    
    return {
        "token": token_string,
        "expires_at": expires_at,
        "user": user
    }
