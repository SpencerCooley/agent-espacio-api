"""
Types definitions - user.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from models.enums import RoleEnum


class CreateUserRequest(BaseModel):
    """Request to create a new user."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")
    role: RoleEnum = Field(default=RoleEnum.user, description="User role (default: user)")


class UpdateUserRequest(BaseModel):
    """Request to update a user."""
    email: Optional[EmailStr] = Field(None, description="New email address")
    role: Optional[RoleEnum] = Field(None, description="New role")
    password: Optional[str] = Field(None, min_length=8, description="New password (minimum 8 characters)")


class PublicUser(BaseModel):
    """Public user information (returned in API responses)."""
    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    role: str = Field(..., description="User role")
    created_at: datetime = Field(..., description="Account creation date")
    is_confirmed: bool = Field(..., description="Whether the account is confirmed")
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Response for listing users."""
    users: list[PublicUser] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")


class DeleteUserResponse(BaseModel):
    """Response for deleting a user."""
    message: str = Field(default="User deleted successfully")
    deleted_user_id: int = Field(..., description="ID of the deleted user")
