"""
Token SQLAlchemy model for bearer token authentication.
"""
from datetime import datetime, timedelta

from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class Token(Base):
    """
    Bearer token for user authentication.
    
    Tokens are stored in the database and expire after 7 days.
    Soft delete via is_active flag - tokens are invalidated when expired or logged out.
    """
    __tablename__ = "tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationship back to user
    user = relationship("User", back_populates="tokens")
    
    def __repr__(self):
        return f"<Token(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"
    
    @staticmethod
    def calculate_expiration() -> datetime:
        """Calculate token expiration (7 days from now)."""
        return datetime.utcnow() + timedelta(days=7)
