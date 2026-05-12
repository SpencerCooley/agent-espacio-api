"""
Role enumeration for users.

Placed in models to avoid circular imports between models and dependencies.
"""
from enum import Enum


class RoleEnum(str, Enum):
    """User roles in the system."""
    admin = "admin"
    user = "user"
