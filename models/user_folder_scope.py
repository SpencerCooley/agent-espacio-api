"""
UserFolderScope SQLAlchemy model for folder-scoped permissions.

Each row grants a user access to a folder and all of its descendants.
Access is the union of all grant rows for that user.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class UserFolderScope(Base):
    """
    Join table: which folders a non-admin user may access.

    - Admin users ignore this table (unrestricted).
    - Editor/member users: access = union of granted folder subtrees.
    - Zero grants = no content access.
    - Grant on the root folder = full-tree access.
    - API keys with user_id inherit that user's grants as permission source.
    """
    __tablename__ = "user_folder_scopes"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="folder_scopes")
    folder = relationship("Folder", back_populates="user_scopes")

    def __repr__(self):
        return f"<UserFolderScope(user_id={self.user_id}, folder_id={self.folder_id})>"
