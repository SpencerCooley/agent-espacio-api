"""
User controller - folder scope grants (admin).
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.folder import Folder
from models.user import User
from models.user_folder_scope import UserFolderScope


def list_user_scopes(db: Session, user_id: int) -> List[UserFolderScope]:
    """List all folder grants for a user."""
    return (
        db.query(UserFolderScope)
        .filter(UserFolderScope.user_id == user_id)
        .order_by(UserFolderScope.created_at.asc())
        .all()
    )


def add_user_scope(
    db: Session,
    user_id: int,
    folder_id: UUID,
) -> Optional[UserFolderScope]:
    """
    Grant a user access to a folder (and its descendants).

    Returns the scope row, or None if user/folder missing.
    Idempotent: returns existing row if grant already present.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        return None

    existing = (
        db.query(UserFolderScope)
        .filter(
            UserFolderScope.user_id == user_id,
            UserFolderScope.folder_id == folder_id,
        )
        .first()
    )
    if existing:
        return existing

    scope = UserFolderScope(user_id=user_id, folder_id=folder_id)
    db.add(scope)
    db.commit()
    db.refresh(scope)
    return scope


def remove_user_scope(db: Session, user_id: int, folder_id: UUID) -> bool:
    """Remove a folder grant. Returns True if a row was deleted."""
    row = (
        db.query(UserFolderScope)
        .filter(
            UserFolderScope.user_id == user_id,
            UserFolderScope.folder_id == folder_id,
        )
        .first()
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
