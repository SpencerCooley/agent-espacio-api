"""
Types definitions - asset.

Pydantic schemas for asset (file) operations.
"""
from datetime import datetime
from typing import Any, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    """Asset information returned in API responses."""
    id: UUID = Field(..., description="Asset ID")
    name: str = Field(..., description="Original filename")
    storage_filename: str = Field(..., description="Filename on disk (includes asset ID)")
    mime_type: str = Field(..., description="MIME type of the file")
    size_bytes: int = Field(..., description="File size in bytes")
    human_readable_size: str = Field(..., description="Human readable file size (e.g., '1.5 MB')")
    folder_id: Optional[UUID] = Field(..., description="Parent folder ID (null if in root)")
    is_image: bool = Field(..., description="Whether this is an image file")
    is_markdown: bool = Field(..., description="Whether this is a markdown file")
    file_extension: str = Field(..., description="File extension")
    file_meta: Optional[dict[str, Any]] = Field(None, description="Extensible metadata (thumbnails, dimensions, EXIF, etc.)")
    descendant_of: Optional[UUID] = Field(..., description="Parent asset ID if this is a transformation")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by_id: int | None = Field(None, description="ID of user who uploaded the asset")
    
    class Config:
        from_attributes = True


class AssetListResponse(BaseModel):
    """Response for listing assets."""
    assets: List[AssetResponse] = Field(..., description="List of assets")
    total: int = Field(..., description="Total number of assets")


class DeleteAssetResponse(BaseModel):
    """Response for deleting an asset."""
    message: str = Field(default="Asset deleted successfully")
    deleted_asset_id: UUID = Field(..., description="ID of the deleted asset")
    deleted_file: bool = Field(..., description="Whether the file was successfully deleted from storage")


class CreateAssetAsDescendantRequest(BaseModel):
    """Request to create a new asset as a descendant of another (transformation)."""
    parent_asset_id: UUID = Field(..., description="ID of the parent asset")
    folder_id: Optional[UUID] = Field(None, description="Target folder (defaults to parent's folder)")
    name: Optional[str] = Field(None, description="New filename (defaults to parent's name with suffix)")


class UpdateAssetRequest(BaseModel):
    """Request to update an asset."""
    name: Optional[str] = Field(None, description="New filename")
    folder_id: Optional[UUID] = Field(None, description="New parent folder ID")


class AssetUploadResponse(BaseModel):
    """Response for successful file upload."""
    message: str = Field(default="File uploaded successfully")
    asset: AssetResponse = Field(..., description="Created asset information")
