"""
API Key SQLAlchemy model for agent authentication.
"""
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class APIKey(Base):
    """
    API key for AI agent authentication.

    Identity is always "agent" (actor.type stays agent; created_by_id stays null).
    Optional user_id is a permission source only:
    - user_id set → inherits that user's folder grants
    - user_id null → global (unrestricted) key

    Soft delete via is_active. Full key shown only once on creation.
    Format: agent-esp-{32-char-hex}
    """
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Human-readable name
    key_hash = Column(String, unique=True, index=True, nullable=False)  # SHA-256 hash
    prefix = Column(String, index=True, nullable=False)  # First 16 chars for display
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete flag
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)  # Track last usage
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    user = relationship("User", back_populates="api_keys")
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.prefix}, is_active={self.is_active}, user_id={self.user_id})>"
