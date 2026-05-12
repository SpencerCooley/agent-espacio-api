"""
User controller - create user.
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User
from models.enums import RoleEnum
from utils.password import hash_password


def create_user(
    db: Session, 
    email: str, 
    password: str, 
    role: RoleEnum = RoleEnum.user
) -> Optional[User]:
    """
    Create a new user.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password (will be hashed)
        role: User role (default: user)
        
    Returns:
        User object if created successfully, None if email already exists
    """
    # Check if email already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return None
    
    # Hash password
    hashed = hash_password(password)
    
    # Create user
    user = User(
        email=email,
        hashed_password=hashed,
        role=role,
        is_confirmed=True  # Auto-confirmed (no email flow)
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user
