"""
Types definitions - folder.

Pydantic schemas for folder operations.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field

from types_definitions.asset import AssetResponse


class CreateFolderRequest(BaseModel):
    """Request to create a new folder."""
    name: str = Field(..., min_length=1, max_length=255, description="Folder name")
    parent_id: Optional[UUID] = Field(None, description="Parent folder ID (null for root)")


class UpdateFolderRequest(BaseModel):
    """Request to update a folder."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="New folder name")
    parent_id: Optional[UUID] = Field(None, description="New parent folder ID (for moving folders)")


class FolderResponse(BaseModel):
    """Folder information returned in API responses."""
    id: UUID = Field(..., description="Folder ID")
    name: str = Field(..., description="Folder name")
    parent_id: Optional[UUID] = Field(..., description="Parent folder ID")
    path: str = Field(..., description="Materialized path in folder tree")
    is_root: bool = Field(..., description="Whether this is the system root folder")
    depth: int = Field(..., description="Depth in folder tree (0 = root)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by_id: int | None = Field(None, description="ID of user who created the folder")
    
    class Config:
        from_attributes = True


class FolderTreeItem(BaseModel):
    """Folder item in a tree listing with children."""
    id: UUID = Field(..., description="Folder ID")
    name: str = Field(..., description="Folder name")
    parent_id: Optional[UUID] = Field(..., description="Parent folder ID")
    path: str = Field(..., description="Materialized path")
    is_root: bool = Field(..., description="Whether this is the root folder")
    created_at: datetime = Field(..., description="Creation timestamp")
    children: List["FolderTreeItem"] = Field(default_factory=list, description="Child folders")
    
    class Config:
        from_attributes = True


class FolderListResponse(BaseModel):
    """Response for listing folders."""
    folders: List[FolderTreeItem] = Field(..., description="List of folders")
    total: int = Field(..., description="Total number of folders")


from types_definitions.artifact import FolderItemResponse

class FolderContentsResponse(BaseModel):
    """Response for folder contents (unified list of items)."""
    folder: FolderResponse = Field(..., description="Current folder info")
    items: List[FolderItemResponse] = Field(..., description="Unified list of folders, assets, and artifacts")
    total_items: int = Field(..., description="Total number of items")


class FolderAncestorsResponse(BaseModel):
    """Response for folder ancestor chain."""
    ancestors: List[FolderResponse] = Field(..., description="Ancestor folders from root to the requested folder")


class DeleteFolderResponse(BaseModel):
    """Response for deleting a folder."""
    message: str = Field(default="Folder and all contents deleted successfully")
    deleted_folder_id: UUID = Field(..., description="ID of the deleted folder")
    deleted_subfolders_count: int = Field(..., description="Number of subfolders deleted")
    deleted_assets_count: int = Field(..., description="Number of assets deleted")
