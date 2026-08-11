"""
Types definitions - profile.

Pydantic schemas for profile operations.
"""
from typing import Optional

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    """Profile information returned in API responses."""
    id: int = Field(..., description="Profile ID")
    user_id: int = Field(..., description="User ID")
    display_name: Optional[str] = Field(None, description="Public display name")
    bio: Optional[str] = Field(None, description="Short bio")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    avatar_asset_id: Optional[str] = Field(None, description="Avatar asset UUID")

    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    """Request to update a profile."""
    display_name: Optional[str] = Field(None, max_length=100, description="Public display name")
    bio: Optional[str] = Field(None, max_length=500, description="Short bio")


class PublicProfileResponse(BaseModel):
    """Public profile information (returned in author bylines)."""
    user_id: int = Field(..., description="User ID")
    display_name: Optional[str] = Field(None, description="Public display name")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")

    class Config:
        from_attributes = True


class PublicCompositionInfo(BaseModel):
    """Minimal composition info for profile listings."""
    id: str = Field(..., description="Artifact ID")
    name: str = Field(..., description="Composition name")
    description: Optional[str] = Field(None, description="Composition description")
    cover_url: Optional[str] = Field(None, description="Cover image URL")
    published_at: Optional[str] = Field(None, description="Published date ISO 8601")
    public_magic_id: str = Field(..., description="Public magic ID for viewing")


class PublicProfileWithCompositions(BaseModel):
    """Full public profile with authored compositions."""
    user_id: int = Field(..., description="User ID")
    display_name: Optional[str] = Field(None, description="Public display name")
    bio: Optional[str] = Field(None, description="Short bio")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    compositions: list[PublicCompositionInfo] = Field(..., description="Public compositions authored by this user")
    total: int = Field(0, description="Total number of compositions")
    has_more: bool = Field(False, description="Whether there are more compositions to load")


class PublicAuthorListItem(BaseModel):
    """Author entry for the public authors list."""
    user_id: int = Field(..., description="User ID")
    display_name: str = Field(..., description="Public display name")
    bio: Optional[str] = Field(None, description="Short bio")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    composition_count: int = Field(..., description="Number of public compositions")
    latest_published_at: Optional[str] = Field(None, description="Most recent composition date")
