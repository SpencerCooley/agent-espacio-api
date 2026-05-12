"""
API Key SQLAlchemy model for agent authentication.
"""
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Boolean

from models.base import Base


class APIKey(Base):
    """
    API key for AI agent authentication.
    
    API keys are system-wide (not user-specific) and use soft delete via is_active flag.
    The full key is shown only once on creation - only the hash is stored.
    
    Format: agent-esp-{32-char-hex}
    Example: agent-esp-a3f7b2d8e9c1...
    """
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Human-readable name
    key_hash = Column(String, unique=True, index=True, nullable=False)  # SHA-256 hash
    prefix = Column(String, index=True, nullable=False)  # First 16 chars for display
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete flag
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)  # Track last usage
    
    # Note: No user_id - API keys are system-wide, not user-owned
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.prefix}, is_active={self.is_active})>"
