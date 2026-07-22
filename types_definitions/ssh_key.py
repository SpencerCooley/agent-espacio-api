"""
Pydantic schemas for SSH key endpoints.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AddSshKeyRequest(BaseModel):
    """Request to register an SSH public key for git access."""
    name: str = Field(
        ..., min_length=1, max_length=255,
        description="Descriptive name for this key (e.g., 'laptop', 'desktop', 'agent-node-1')"
    )
    public_key: str = Field(
        ..., min_length=1,
        description="Full OpenSSH public key string (e.g., 'ssh-ed25519 AAAA... user@host')"
    )


class SshKeyResponse(BaseModel):
    """Registered SSH key information."""
    id: int = Field(..., description="Key ID")
    name: str = Field(..., description="Key name")
    fingerprint: str = Field(..., description="SHA256 fingerprint of the key")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")

    class Config:
        from_attributes = True


class SshKeyListResponse(BaseModel):
    """Response for listing SSH keys."""
    keys: list[SshKeyResponse] = Field(default_factory=list, description="List of registered SSH keys")
    total: int = Field(..., description="Total number of keys")


class DeleteSshKeyResponse(BaseModel):
    """Response for deleting an SSH key."""
    message: str = Field(default="SSH key deleted successfully")
    deleted_key_id: int = Field(..., description="ID of the deleted key")
