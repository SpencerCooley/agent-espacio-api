"""
User SQLAlchemy model.
"""
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship

from models.base import Base
from models.enums import RoleEnum


class User(Base):
    """
    User model for authentication and authorization.
    
    Supports two roles:
    - admin: Full system access, can manage users and API keys
    - user: Regular user, can access workspace
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLAlchemyEnum(RoleEnum), nullable=False, default=RoleEnum.user)
    is_confirmed = Column(Boolean, default=True, nullable=False)  # Auto-confirmed (no email flow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - cascade delete when user is deleted
    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    reset_tokens = relationship("ResetToken", back_populates="user", cascade="all, delete-orphan")
    folders = relationship("Folder", back_populates="created_by", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="created_by", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="created_by", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
