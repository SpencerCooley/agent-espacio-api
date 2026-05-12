"""
Type definitions package.

Pydantic schemas for request validation and response serialization.
"""

from types_definitions.auth import (
    UserCredentials,
    AuthToken,
    AuthTokenWithUser,
    TokenValidationResponse,
    LogoutResponse,
    PasswordChangeRequest,
    AdminPasswordResetRequest,
    PasswordResetTokenRequest,
    PasswordResetWithToken,
)

from types_definitions.user import (
    CreateUserRequest,
    UpdateUserRequest,
    PublicUser,
    UserListResponse,
    DeleteUserResponse,
)

from types_definitions.api_key import (
    CreateAPIKeyRequest,
    APIKeyResponse,
    APIKeyListResponse,
    RevokeAPIKeyResponse,
)

from types_definitions.common import (
    ErrorResponse,
    SuccessResponse,
    PaginationParams,
)

__all__ = [
    # Auth
    "UserCredentials",
    "AuthToken",
    "AuthTokenWithUser",
    "TokenValidationResponse",
    "LogoutResponse",
    "PasswordChangeRequest",
    "AdminPasswordResetRequest",
    "PasswordResetTokenRequest",
    "PasswordResetWithToken",
    # User
    "CreateUserRequest",
    "UpdateUserRequest",
    "PublicUser",
    "UserListResponse",
    "DeleteUserResponse",
    # API Key
    "CreateAPIKeyRequest",
    "APIKeyResponse",
    "APIKeyListResponse",
    "RevokeAPIKeyResponse",
    # Common
    "ErrorResponse",
    "SuccessResponse",
    "PaginationParams",
]
