"""
User controller - delete user.
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User
from models.token import Token


def delete_user(db: Session, user_id: int) -> Optional[int]:
    """
    Delete user and all associated data (cascade delete for tokens).
    
    Args:
        db: Database session
        user_id: User ID to delete
        
    Returns:
        Deleted user ID if found, None otherwise
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        return None
    
    # Get user ID before deletion
    deleted_id = user.id
    
    # Delete user (cascade will handle tokens and reset_tokens)
    db.delete(user)
    db.commit()
    
    return deleted_id
