"""
Settings SQLAlchemy model.

A key-value JSON store for global instance settings.
This is intentionally simple - one row per key, value stored as JSON.
"""
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON

from models.base import Base


class Setting(Base):
    """
    Global settings for the application instance.
    
    Currently stores:
    - public_theme: { name: str, mode: 'light' | 'dark' }
    
    Future additions:
    - site_name: str
    - default_folder_permissions: str
    - etc.
    """
    __tablename__ = "settings"
    
    key = Column(String, primary_key=True, index=True)
    value = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Setting(key={self.key}, value={self.value})>"
