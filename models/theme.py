"""
Theme SQLAlchemy model for database-driven MUI themes.

Stores theme definitions as JSONB for both light and dark modes.
Themes are referenced by ID for public views and workspace personalization.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base


class Theme(Base):
    """
    Theme model for storing MUI-compatible theme definitions.

    Each theme contains both light and dark mode definitions as JSONB.
    The frontend resolves the appropriate definition based on the requested mode.
    """
    __tablename__ = "themes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    light_definition = Column(JSON, nullable=False, default=dict)
    dark_definition = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Theme(id={self.id}, name={self.name})>"
