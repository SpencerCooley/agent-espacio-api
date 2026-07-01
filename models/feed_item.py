"""
FeedItem SQLAlchemy model.

Represents a curated inclusion of an artifact in the public feed.
Only artifacts explicitly added here appear in the public feed.
An artifact can appear in the feed at most once (unique artifact_id).
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class FeedItem(Base):
    """
    Feed item for curated public feed.

    Features:
    - One-to-one with artifacts (unique artifact_id constraint)
    - sort_order for manual ordering
    """
    __tablename__ = "feed_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    artifact_id = Column(UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=False, unique=True)
    sort_order = Column(Integer, default=0, server_default='0', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    artifact = relationship("Artifact")

    __table_args__ = (
        Index('ix_feed_items_sort_order', 'sort_order'),
        Index('ix_feed_items_updated_at', 'updated_at'),
        UniqueConstraint('artifact_id', name='uq_feed_items_artifact_id'),
    )

    def __repr__(self):
        return f"<FeedItem(id={self.id}, artifact_id={self.artifact_id}, sort_order={self.sort_order})>"
