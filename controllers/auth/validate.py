"""
Authentication controller - token validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from models.token import Token
from models.user import User


def validate_token(db: Session, token_string: str) -> Optional[Dict[str, Any]]:
    """
    Validate a bearer token.
    
    Args:
        db: Database session
        token_string: Bearer token to validate
        
    Returns:
        dict with valid status, user (if valid), and message
    """
    token = db.query(Token).filter(Token.token == token_string).first()
    
    if not token:
        return {
            "valid": False,
            "user": None,
            "message": "Token not found"
        }
    
    if not token.is_active:
        return {
            "valid": False,
            "user": None,
            "message": "Token is inactive"
        }
    
    if token.expires_at < datetime.utcnow():
        # Mark as inactive
        token.is_active = False
        db.commit()
        return {
            "valid": False,
            "user": None,
            "message": "Token has expired"
        }
    
    return {
        "valid": True,
        "user": token.user,
        "message": "Token is valid"
    }
