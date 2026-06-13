"""
Artifact SQLAlchemy model for non-file workspace items.

Artifacts represent rich, interactive content stored as JSONB configurations.
They live in folders alongside assets. Examples: maps, charts, 3D scenes, etc.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from models.base import Base


class Artifact(Base):
    """
    Artifact model for interactive, non-file content items.
    
    Features:
    - Stored in folders alongside assets
    - Content stored as JSONB for maximum flexibility
    - Type field for frontend renderer selection and AI documentation lookup
    - Optional description field for AI context ("readme")
    """
    __tablename__ = "artifacts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    type = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    content = Column(JSONB, nullable=False, default=dict)
    folder_id = Column(UUID(as_uuid=True), ForeignKey("folders.id"), nullable=False, index=True)
    is_public = Column(Boolean, default=False, server_default='false', nullable=False)
    public_magic_id = Column(UUID(as_uuid=True), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Relationships
    folder = relationship("Folder", back_populates="artifacts")
    created_by = relationship("User", back_populates="artifacts")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_artifacts_type', 'type'),
        Index('ix_artifacts_folder_type', 'folder_id', 'type'),
        Index('ix_artifacts_created_at', 'created_at'),
        Index('ix_artifacts_public_magic_id', 'public_magic_id', unique=True),
    )
    
    def __repr__(self):
        return f"<Artifact(id={self.id}, name='{self.name}', type='{self.type}')>"
