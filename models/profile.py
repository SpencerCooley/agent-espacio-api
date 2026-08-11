"""
Profile SQLAlchemy model for user public identity.

Profiles store public identity information for users, separate from authentication.
Each user has exactly one profile (one-to-one relationship).
Avatar assets are stored without folder_id (system asset pattern, hidden from folder listings).
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from models.base import Base


class Profile(Base):
    """
    Profile model for user public identity.
    
    Features:
    - One-to-one with User (each user has one profile)
    - Display name for public attribution
    - Optional bio
    - Avatar stored as asset without folder (hidden from folder listings)
    - Auto-created empty profile for new users
    """
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # Public identity
    display_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    
    # Avatar is stored as derivative files (like gallery covers)
    # avatar_user_id stores the user_id to construct the file path: derived/avatars/{user_id}_{size}.webp
    avatar_user_id = Column(Integer, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="profile")
    
    def __repr__(self):
        return f"<Profile(id={self.id}, user_id={self.user_id}, display_name='{self.display_name}')>"
