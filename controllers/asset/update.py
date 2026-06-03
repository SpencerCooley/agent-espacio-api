"""
Asset controller - update asset.
"""
import os
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.asset import Asset
from models.folder import Folder
from services.file_storage import write_file, get_asset_path


def update_asset(
    db: Session,
    asset: Asset,
    name: Optional[str] = None,
    folder_id: Optional[UUID] = None,
    content: Optional[str] = None,
) -> Asset:
    """
    Update an asset's name, move it to a different folder, or update its content.

    Args:
        db: Database session
        asset: Asset object to update
        name: New filename
        folder_id: New parent folder ID (for moving)
        content: New file content (for text files like markdown)

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

    # Update file content if provided
    if content is not None:
        file_path = get_asset_path(asset.storage_filename)
        write_file(asset.storage_filename, content)
        new_size = os.path.getsize(file_path)
        asset.size_bytes = new_size

    db.commit()
    db.refresh(asset)

    return asset
