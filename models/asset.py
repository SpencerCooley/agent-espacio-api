"""
Asset SQLAlchemy model for file metadata and storage.

Assets represent files stored on disk with their metadata tracked in the database.
Supports descendant tracking for transformations (e.g., AI-generated variations).
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from models.base import Base


class Asset(Base):
    """
    Asset model representing a file stored in the system.
    
    Features:
    - Stored with ID-based naming for easy correlation with DB records
    - MIME type detection for content type identification
    - File size tracking
    - Descendant tracking for transformation workflows
    - Belongs to a folder (or root if folder_id is NULL)
    - JSONB file_meta for extensible metadata (thumbnails, EXIF, dimensions, etc.)
    
    On-disk naming: {asset_id}_{sanitized_filename}
    Example: 550e8400-e29b-41d4-a716-446655440000_photo.png
    
    Thumbnail naming: {asset_id}_thumb_{size}.webp
    Example: 550e8400-e29b-41d4-a716-446655440000_thumb_256.webp
    """
    __tablename__ = "assets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)  # Original filename
    storage_filename = Column(String(300), nullable=False)  # Actual filename on disk: "{uuid}_{name}"
    mime_type = Column(String(100), nullable=False, default="application/octet-stream")
    size_bytes = Column(BigInteger, nullable=False, default=0)
    file_meta = Column(JSONB, nullable=True, default=None)  # Extensible metadata: thumbnails, EXIF, dimensions, etc.
    folder_id = Column(UUID(as_uuid=True), ForeignKey("folders.id"), nullable=True, index=True)
    descendant_of = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Relationships
    folder = relationship("Folder", back_populates="assets")
    parent_asset = relationship(
        "Asset",
        back_populates="descendants",
        remote_side=[id],
        cascade="all"
    )
    descendants = relationship(
        "Asset",
        back_populates="parent_asset",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    created_by = relationship("User", back_populates="assets")
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_assets_mime_type', 'mime_type'),
        Index('ix_assets_created_at', 'created_at'),
        Index('ix_assets_folder_mime', 'folder_id', 'mime_type'),
    )
    
    def __repr__(self):
        return f"<Asset(id={self.id}, name='{self.name}', mime_type='{self.mime_type}')>"
    
    @property
    def file_extension(self):
        """Extract file extension from original filename."""
        if "." in self.name:
            return self.name.rsplit(".", 1)[-1].lower()
        return ""
    
    @property
    def is_image(self):
        """Check if asset is an image based on MIME type."""
        return self.mime_type.startswith("image/")
    
    @property
    def is_markdown(self):
        """Check if asset is a markdown file."""
        return self.mime_type in ("text/markdown", "text/x-markdown") or \
               self.file_extension in ("md", "markdown")
    
    @property
    def human_readable_size(self):
        """Convert size_bytes to human readable format."""
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    @property
    def available_thumbnails(self) -> list[int]:
        """Return list of available thumbnail sizes (e.g., [256, 512]) from file_meta."""
        if not self.file_meta or "thumbnails" not in self.file_meta:
            return []
        return [int(s) for s in self.file_meta["thumbnails"].keys()]
    
    @property
    def image_dimensions(self) -> tuple[int, int] | None:
        """Return (width, height) from file_meta if available."""
        if not self.file_meta:
            return None
        w = self.file_meta.get("width")
        h = self.file_meta.get("height")
        if w and h:
            return (w, h)
        return None
    
    def get_thumbnail_filename(self, size: int) -> str:
        """Get the storage filename for a thumbnail of the given size."""
        return f"{self.id}_thumb_{size}.webp"
    
    def get_storage_path(self, base_path="/app/storage"):
        """Return the full storage path for this asset."""
        import os
        return os.path.join(base_path, "assets", self.storage_filename)
