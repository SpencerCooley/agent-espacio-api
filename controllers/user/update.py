"""
User controller - update user.
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User
from models.enums import RoleEnum
from utils.password import hash_password


def update_user(
    db: Session,
    user_id: int,
    email: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[RoleEnum] = None
) -> Optional[User]:
    """
    Update user information.
    
    Args:
        db: Database session
        user_id: User ID to update
        email: New email (optional)
        password: New password (optional, will be hashed)
        role: New role (optional)
        
    Returns:
        Updated User object if found, None otherwise
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        return None
    
    # Check email uniqueness if changing email
    if email and email != user.email:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return None  # Email already in use
        user.email = email
    
    # Update password if provided
    if password:
        user.hashed_password = hash_password(password)
    
    # Update role if provided
    if role:
        user.role = role
    
    db.commit()
    db.refresh(user)
    
    return user
