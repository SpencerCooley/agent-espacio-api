"""
Routers package.

Contains all API endpoint routers:
- ai_instructions: Unauthenticated AI agent onboarding
- health: Health check endpoints
- auth: Authentication endpoints
- users: User management endpoints
- api_keys: API key management endpoints
- folders: Folder management endpoints
- assets: Asset (file) management endpoints
- artifacts: Artifact (non-file) management endpoints
- public: Public view endpoints
- settings: Global settings endpoints
- themes: Theme management endpoints
- feed: Curated public feed endpoints
- ws: WebSocket endpoints
"""

from . import ai_instructions
from . import health
from . import auth
from . import users
from . import api_keys
from . import folders
from . import assets
from . import artifacts
from . import public
from . import settings
from . import themes
from . import feed
from . import ws

__all__ = ["ai_instructions", "health", "auth", "users", "api_keys", "folders", "assets", "artifacts", "public", "settings", "themes", "feed", "ws"]
