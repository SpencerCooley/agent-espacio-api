"""
Folder SQLAlchemy model for hierarchical file storage.

Supports unlimited nesting of folders (tree structure).
Root folder "My Drive" is a system folder that cannot be deleted.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class Folder(Base):
    """
    Folder model for organizing assets in a hierarchical structure.
    
    Features:
    - Unlimited nesting (parent-child relationships)
    - Materialized path for fast tree traversal
    - System root folder that cannot be deleted
    - Recursive delete support (deletes all contents)
    """
    __tablename__ = "folders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("folders.id"), nullable=True, index=True)
    path = Column(String(1024), nullable=False, default="/")
    is_root = Column(Boolean, default=False, nullable=False)
    is_public = Column(Boolean, default=False, server_default='false', nullable=False)
    public_magic_id = Column(UUID(as_uuid=True), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Relationships
    parent = relationship(
        "Folder",
        back_populates="children",
        remote_side=[id]
    )
    children = relationship(
        "Folder",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    assets = relationship(
        "Asset",
        back_populates="folder",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    artifacts = relationship(
        "Artifact",
        back_populates="folder",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    created_by = relationship("User", back_populates="folders")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_folders_path', 'path'),
        Index('ix_folders_name_parent', 'name', 'parent_id'),
        Index('ix_folders_public_magic_id', 'public_magic_id', unique=True),
    )
    
    def __repr__(self):
        return f"<Folder(id={self.id}, name='{self.name}', path='{self.path}')>"
    
    @property
    def full_path(self):
        """Return the full materialized path for this folder."""
        if self.is_root:
            return "/"
        return self.path
    
    @property
    def depth(self):
        """Calculate the depth of this folder in the tree (0 = root)."""
        if self.is_root or not self.parent_id:
            return 0
        return self.path.count("/") - 1
    
    def build_path(self):
        """Build and set the materialized path based on parent."""
        if self.is_root:
            self.path = "/"
        elif self.parent:
            parent_path = self.parent.path.rstrip("/")
            self.path = f"{parent_path}/{self.name}/"
        else:
            self.path = f"/{self.name}/"
        return self.path
