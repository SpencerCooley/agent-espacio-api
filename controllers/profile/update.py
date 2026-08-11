"""
Profile update controller.

Handles updating profile fields.
"""
from sqlalchemy.orm import Session

from models import Profile
from types_definitions.profile import ProfileUpdateRequest


def update_profile(db: Session, profile: Profile, data: ProfileUpdateRequest) -> Profile:
    """
    Update a profile's fields.
    
    Args:
        db: Database session
        profile: Profile object to update
        data: Update data
        
    Returns:
        Updated Profile object
    """
    if data.display_name is not None:
        profile.display_name = data.display_name
    if data.bio is not None:
        profile.bio = data.bio
    
    db.commit()
    db.refresh(profile)
    return profile
