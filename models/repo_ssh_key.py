"""
Repo SSH key model for git repository authentication.

Users register SSH public keys to push to repository artifacts.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index

from models.base import Base


class RepoSshKey(Base):
    """
    SSH public key for git repository access.
    
    Users can register multiple SSH keys (e.g., laptop, desktop, agent machines).
    Keys are used by the git SSH container to authenticate push/pull operations.
    """
    __tablename__ = "repo_ssh_keys"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    public_key = Column(Text, nullable=False)
    fingerprint = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Composite index for fast user key lookups
    __table_args__ = (
        Index('ix_repo_ssh_keys_user_id', 'user_id'),
    )
    
    def __repr__(self):
        return f"<RepoSshKey(id={self.id}, user_id={self.user_id}, name='{self.name}')>"
