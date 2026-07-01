"""
Types definitions - artifact.

Pydantic schemas for artifact operations.
"""
from datetime import datetime
from typing import Any, Dict, Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class CreateArtifactRequest(BaseModel):
    """Request to create a new artifact."""
    name: str = Field(..., min_length=1, max_length=255, description="Artifact display name")
    type: str = Field(..., min_length=1, max_length=255, description="Artifact type key (e.g., 'note')")
    description: Optional[str] = Field(None, description="Optional readme/description for AI context")
    content: dict[str, Any] = Field(..., description="Artifact content as JSONB (structure depends on type)")
    folder_id: UUID = Field(..., description="Parent folder ID")


class UpdateArtifactRequest(BaseModel):
    """Request to update an artifact. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="New artifact name")
    type: Optional[str] = Field(None, min_length=1, max_length=255, description="New artifact type key")
    description: Optional[str] = Field(None, description="New description")
    content: Optional[dict[str, Any]] = Field(None, description="New content JSONB")
    meta: Optional[dict[str, Any]] = Field(None, description="New metadata JSONB")
    folder_id: Optional[UUID] = Field(None, description="New parent folder ID (for moving)")


class ArtifactResponse(BaseModel):
    """Artifact information returned in API responses."""
    id: UUID = Field(..., description="Artifact ID")
    name: str = Field(..., description="Artifact display name")
    type: str = Field(..., description="Artifact type key")
    description: Optional[str] = Field(None, description="Description/readme for AI context")
    content: dict[str, Any] = Field(..., description="Artifact content JSONB")
    meta: Optional[dict[str, Any]] = Field(None, description="Artifact metadata JSONB")
    folder_id: UUID = Field(..., description="Parent folder ID")
    is_public: bool = Field(..., description="Whether this artifact is publicly shared")
    public_magic_id: Optional[UUID] = Field(None, description="Public share magic link ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by_id: Optional[int] = Field(None, description="ID of user who created the artifact")

    class Config:
        from_attributes = True


class ArtifactListResponse(BaseModel):
    """Response for listing artifacts."""
    artifacts: List[ArtifactResponse] = Field(..., description="List of artifacts")
    total: int = Field(..., description="Total number of artifacts")


class DeleteArtifactResponse(BaseModel):
    """Response for deleting an artifact."""
    message: str = Field(default="Artifact deleted successfully")
    deleted_artifact_id: UUID = Field(..., description="ID of the deleted artifact")


class ArtifactTypeResponse(BaseModel):
    """Single artifact type definition from the registry."""
    key: str = Field(..., description="Type key")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Short description")
    ai_instructions: str = Field(..., description="Instructions for AI agents")
    content_schema: dict[str, Any] = Field(..., description="JSON schema for content validation")
    example_content: dict[str, Any] = Field(..., description="Example of valid content")
    icon: str = Field(..., description="Icon identifier")
    category: str = Field(..., description="Category for grouping")


class ArtifactTypeListResponse(BaseModel):
    """Response for listing all artifact type definitions."""
    types: List[ArtifactTypeResponse] = Field(..., description="List of artifact type definitions")
    total: int = Field(..., description="Total number of types")


class PreviewArtifactResponse(BaseModel):
    """Response for artifact preview - same format as public view."""
    kind: str = Field(default="artifact", description="Item kind")
    artifact: Dict[str, Any] = Field(..., description="Artifact data matching public view format")
    public_theme: Dict[str, Any] = Field(..., description="Public theme settings with resolved definition")


class CompositionSectionResponse(BaseModel):
    """A single section within a composition, with resolved artifact."""
    artifact: Optional[Dict[str, Any]] = Field(None, description="Resolved artifact data (null if not found or not public)")
    caption: Optional[str] = Field(None, description="Optional caption text")
    artifact_id: Optional[str] = Field(None, description="Referenced artifact UUID")


class CompositionResponse(BaseModel):
    """Response for resolving a composer artifact with all sub-artifacts."""
    composer: Dict[str, Any] = Field(..., description="The composer artifact data")
    sections: List[CompositionSectionResponse] = Field(..., description="Resolved sections in order")


class FolderItemResponse(BaseModel):
    """
    Unified item representation for folder contents.
    
    Can represent a folder, asset, or artifact in a single list.
    The 'kind' field indicates which type of item it is.
    """
    kind: str = Field(..., description="Item kind: 'folder', 'asset', or 'artifact'")
    id: UUID = Field(..., description="Item ID")
    name: str = Field(..., description="Item display name")
    type: Optional[str] = Field(None, description="Artifact type key (only for artifacts)")
    mime_type: Optional[str] = Field(None, description="MIME type (only for assets)")
    size_bytes: Optional[int] = Field(None, description="File size in bytes (only for assets)")
    is_image: Optional[bool] = Field(None, description="Whether asset is an image (only for assets)")
    file_meta: Optional[dict[str, Any]] = Field(None, description="Extensible metadata (only for assets)")
    is_public: bool = Field(..., description="Whether this item is publicly shared")
    public_magic_id: Optional[UUID] = Field(None, description="Public share magic link ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True
