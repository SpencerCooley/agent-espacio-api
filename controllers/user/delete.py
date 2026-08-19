"""
User controller - delete user.
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.user import User
from models.api_key import APIKey


def delete_user(db: Session, user_id: int) -> Optional[int]:
    """
    Delete user and all associated data (cascade delete for tokens/scopes).

    API keys assigned to this user have user_id set to NULL (become global).
    
    Args:
        db: Database session
        user_id: User ID to delete
        
    Returns:
        Deleted user ID if found, None otherwise
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        return None
    
    deleted_id = user.id

    # Detach API keys so they become global rather than cascade-deleted
    db.query(APIKey).filter(APIKey.user_id == user_id).update(
        {APIKey.user_id: None},
        synchronize_session=False,
    )
    
    # Delete user (cascade handles tokens + folder_scopes)
    db.delete(user)
    db.commit()
    
    return deleted_id
