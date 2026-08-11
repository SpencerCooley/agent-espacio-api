"""
Profile controllers.

Handles profile CRUD operations and avatar upload.
"""
from controllers.profile.get import (
    get_or_create_profile,
    get_public_profile,
    get_authored_public_compositions,
    list_public_authors,
)
from controllers.profile.update import update_profile
from controllers.profile.avatar import upload_avatar

__all__ = [
    "get_or_create_profile",
    "get_public_profile",
    "get_authored_public_compositions",
    "list_public_authors",
    "update_profile",
    "upload_avatar",
]