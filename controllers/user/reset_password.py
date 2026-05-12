"""
User controller - password reset.
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User
from models.reset_token import ResetToken
from utils.password import hash_password
from utils.token import generate_reset_token


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


def create_reset_token(db: Session, user_id: int) -> Optional[str]:
    """
    Create a password reset token for a user.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Reset token string if user exists, None otherwise
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        return None
    
    # Generate token
    token_string = generate_reset_token()
    expires_at = ResetToken.calculate_expiration()
    
    # Create token record
    reset_token = ResetToken(
        token=token_string,
        expires_at=expires_at,
        user_id=user_id
    )
    
    db.add(reset_token)
    db.commit()
    
    return token_string


def reset_password_with_token(db: Session, token_string: str, new_password: str) -> Optional[User]:
    """
    Reset password using a reset token.
    
    Args:
        db: Database session
        token_string: Reset token
        new_password: New plain text password (will be hashed)
        
    Returns:
        Updated User object if token is valid, None otherwise
    """
    reset_token = db.query(ResetToken).filter(ResetToken.token == token_string).first()
    
    if not reset_token:
        return None
    
    # Check if token is valid
    if not reset_token.is_valid():
        return None
    
    # Get user
    user = reset_token.user
    
    # Hash and set new password
    user.hashed_password = hash_password(new_password)
    
    # Mark token as used
    reset_token.is_used = True
    
    # Invalidate all existing tokens
    tokens = db.query(Token).filter(
        Token.user_id == user.id,
        Token.is_active == True
    ).all()
    
    for token in tokens:
        token.is_active = False
    
    db.commit()
    db.refresh(user)
    
    return user
