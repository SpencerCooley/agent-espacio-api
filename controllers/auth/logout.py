"""
Authentication controller - logout.
"""
from sqlalchemy.orm import Session

from models.token import Token


def logout(db: Session, token_string: str) -> bool:
    """
    Logout user by invalidating their token.
    
    Args:
        db: Database session
        token_string: Bearer token to invalidate
        
    Returns:
        bool: True if token was found and invalidated, False otherwise
    """
    token = db.query(Token).filter(Token.token == token_string).first()
    
    if not token:
        return False
    
    # Soft delete - mark as inactive
    token.is_active = False
    db.commit()
    
    return True


def logout_all_sessions(db: Session, user_id: int) -> int:
    """
    Logout all sessions for a user (invalidate all their tokens).
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        int: Number of tokens invalidated
    """
    tokens = db.query(Token).filter(
        Token.user_id == user_id,
        Token.is_active == True
    ).all()
    
    count = 0
    for token in tokens:
        token.is_active = False
        count += 1
    
    db.commit()
    
    return count
