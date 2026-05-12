"""
User controller - list users.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from models.user import User
from models.enums import RoleEnum


def list_users(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    role: Optional[RoleEnum] = None
) -> List[User]:
    """
    List users with optional filtering.
    
    Args:
        db: Database session
        skip: Number of users to skip (pagination)
        limit: Maximum number of users to return (pagination)
        role: Optional role filter
        
    Returns:
        List of User objects
    """
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    
    return query.offset(skip).limit(limit).all()


def count_users(db: Session, role: Optional[RoleEnum] = None) -> int:
    """
    Count total number of users.
    
    Args:
        db: Database session
        role: Optional role filter
        
    Returns:
        Total count of users
    """
    query = db.query(User)
    
    if role:
        query = query.filter(User.role == role)
    
    return query.count()
