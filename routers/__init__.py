"""
Routers package.

Contains all API endpoint routers:
- auth: Authentication endpoints
- users: User management endpoints
- api_keys: API key management endpoints
- folders: Folder management endpoints
- assets: Asset (file) management endpoints
"""

from . import health
from . import auth
from . import users
from . import api_keys
from . import folders
from . import assets

__all__ = ["health", "auth", "users", "api_keys", "folders", "assets"]
