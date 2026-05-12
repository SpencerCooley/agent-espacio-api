"""
Common Pydantic schemas used across endpoints.
"""
from typing import Optional, Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for client handling")


class SuccessResponse(BaseModel):
    """Standard success response."""
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Optional data payload")


class PaginationParams(BaseModel):
    """Common pagination parameters."""
    skip: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of items to return")
