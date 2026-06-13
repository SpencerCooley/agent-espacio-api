"""
Asset controller - share toggle.
"""
from uuid import uuid4, UUID

from sqlalchemy.orm import Session

from models.asset import Asset


def toggle_asset_share(db: Session, asset: Asset) -> Asset:
    """
    Toggle an asset's public sharing status.
    
    If currently private, makes it public and generates a public_magic_id.
    If currently public, makes it private and clears the public_magic_id.
    
    Args:
        db: Database session
        asset: Asset to toggle
        
    Returns:
        Updated asset object
    """
    if asset.is_public:
        asset.is_public = False
        asset.public_magic_id = None
    else:
        asset.is_public = True
        asset.public_magic_id = uuid4()
    
    db.commit()
    db.refresh(asset)
    return asset
