"""
Types definitions - auth.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from models.enums import RoleEnum


class UserCredentials(BaseModel):
    """User login credentials."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")


class AuthToken(BaseModel):
    """Authentication token response."""
    token: str = Field(..., description="Bearer token for authentication")
    expires_at: datetime = Field(..., description="Token expiration date")
    
    class Config:
        from_attributes = True


class AuthTokenWithUser(AuthToken):
    """Authentication token with user information."""
    user: "PublicUser" = Field(..., description="Authenticated user")


class TokenValidationResponse(BaseModel):
    """Token validation response."""
    valid: bool = Field(..., description="Whether the token is valid")
    user: Optional["PublicUser"] = Field(None, description="User if token is valid")
    message: str = Field(..., description="Validation message")


class LogoutResponse(BaseModel):
    """Logout response."""
    message: str = Field(default="Logged out successfully")


class PasswordChangeRequest(BaseModel):
    """Password change request (for logged-in users)."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


class AdminPasswordResetRequest(BaseModel):
    """Admin password reset request."""
    new_password: str = Field(..., min_length=8, description="New password for the user (minimum 8 characters)")


class PasswordResetTokenRequest(BaseModel):
    """Request a password reset token (for user self-service)."""
    email: EmailStr


class PasswordResetWithToken(BaseModel):
    """Reset password using a reset token."""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password (minimum 8 characters)")


# Import at the end to avoid circular imports
from types_definitions.user import PublicUser
