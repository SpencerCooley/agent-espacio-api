"""
Asset controller - update asset.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.asset import Asset
from models.folder import Folder


def update_asset(
    db: Session,
    asset: Asset,
    name: Optional[str] = None,
    folder_id: Optional[UUID] = None,
) -> Asset:
    """
    Update an asset's name or move it to a different folder.

    Args:
        db: Database session
        asset: Asset object to update
        name: New filename
        folder_id: New parent folder ID (for moving)

    Returns:
        Updated asset object

    Raises:
        ValueError: If new folder not found
    """
    # Update name if provided
    if name is not None:
        asset.name = name

    # Move to new folder if provided
    if folder_id is not None and folder_id != asset.folder_id:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            raise ValueError("Target folder not found")
        asset.folder_id = folder_id

    db.commit()
    db.refresh(asset)

    return asset
