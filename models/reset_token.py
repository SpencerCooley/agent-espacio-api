"""
Reset Token SQLAlchemy model for password reset.
"""
from datetime import datetime, timedelta

from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class ResetToken(Base):
    """
    Token for password reset flow.
    
    Admin can generate reset tokens for users who forgot their password.
    Tokens expire after 24 hours and can only be used once (is_used flag).
    """
    __tablename__ = "reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationship back to user
    user = relationship("User", back_populates="reset_tokens")
    
    def __repr__(self):
        return f"<ResetToken(id={self.id}, user_id={self.user_id}, is_used={self.is_used})>"
    
    @staticmethod
    def calculate_expiration() -> datetime:
        """Calculate reset token expiration (24 hours from now)."""
        return datetime.utcnow() + timedelta(hours=24)
    
    def is_valid(self) -> bool:
        """Check if token is valid (not used and not expired)."""
        if self.is_used:
            return False
        if self.expires_at < datetime.utcnow():
            return False
        return True
