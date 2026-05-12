"""
Pydantic schemas for API key endpoints.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=100, 
                       description="Name for the API key (e.g., 'laptop-main', 'openclaw-node-1')")


class APIKeyResponse(BaseModel):
    """API key information."""
    id: int = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    key: Optional[str] = Field(None, description="The actual API key (only shown once on creation)")
    prefix: str = Field(..., description="First 16 characters of the key for identification")
    created_at: datetime = Field(..., description="Creation date")
    last_used_at: Optional[datetime] = Field(None, description="Last usage date")
    is_active: bool = Field(..., description="Whether the key is active")
    
    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """Response for listing API keys."""
    keys: list[APIKeyResponse] = Field(..., description="List of API keys")
    total: int = Field(..., description="Total number of API keys")


class RevokeAPIKeyResponse(BaseModel):
    """Response for revoking an API key."""
    message: str = Field(default="API key revoked successfully")
    revoked_key_id: int = Field(..., description="ID of the revoked API key")
