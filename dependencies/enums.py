"""
Role enumeration re-exported from models.

This avoids circular imports - the canonical definition is in models/enums.py.
"""
from models.enums import RoleEnum

__all__ = ["RoleEnum"]
