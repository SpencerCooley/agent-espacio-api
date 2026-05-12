"""
Dependencies package.

Contains:
- enums.py: RoleEnum re-exported from models.enums
- dependencies.py: Authentication and permission dependencies
"""

from dependencies.enums import RoleEnum
from dependencies.dependencies import (
    get_db,
    get_current_user,
    get_current_user_optional,
    get_current_api_key,
    get_current_api_key_optional,
    require_admin,
    require_user,
    allow_agent_api_key,
    oauth2_scheme,
    oauth2_scheme_optional,
)

__all__ = [
    "RoleEnum",
    "get_db",
    "get_current_user",
    "get_current_user_optional",
    "get_current_api_key",
    "get_current_api_key_optional",
    "require_admin",
    "require_user",
    "allow_agent_api_key",
    "oauth2_scheme",
    "oauth2_scheme_optional",
]
