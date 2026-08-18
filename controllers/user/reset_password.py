"""
User controller - password reset.
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User
from utils.password import hash_password


def admin_reset_password(db: Session, user_id: int, new_password: str) -> Optional[User]:
    """
    Admin reset user password directly.
    
    Args:
        db: Database session
        user_id: User ID
        new_password: New plain text password (will be hashed)
        
    Returns:
        Updated User object if found, None otherwise
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        return None
    
    # Hash and set new password
    user.hashed_password = hash_password(new_password)
    
    # Invalidate all existing tokens (force re-login)
    tokens = db.query(Token).filter(
        Token.user_id == user_id,
        Token.is_active == True
    ).all()
    
    for token in tokens:
        token.is_active = False
    
    db.commit()
    db.refresh(user)
    
    return user


def change_own_password(
    db: Session, 
    user_id: int, 
    current_password: str, 
    new_password: str
) -> Optional[User]:
    """
    User changes their own password (requires current password).
    
    Args:
        db: Database session
        user_id: User ID
        current_password: Current plain text password (for verification)
        new_password: New plain text password (will be hashed)
        
    Returns:
        Updated User object if successful, None otherwise
    """
    from utils.password import verify_password
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        return None
    
    # Verify current password
    if not verify_password(current_password, user.hashed_password):
        return None
    
    # Hash and set new password
    user.hashed_password = hash_password(new_password)
    
    # Invalidate all existing tokens (force re-login)
    tokens = db.query(Token).filter(
        Token.user_id == user_id,
        Token.is_active == True
    ).all()
    
    for token in tokens:
        token.is_active = False
    
    db.commit()
    db.refresh(user)
    
    return user
