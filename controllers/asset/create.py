"""
Asset controller - create asset.
"""
import os
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from models.asset import Asset
from models.folder import Folder
from models.user import User
from services.file_storage import (
    get_mime_type,
    generate_storage_filename,
    save_uploaded_file,
    validate_file_size,
)


def create_asset(
    db: Session,
    name: str,
    temp_file_path: str,
    created_by: User,
    folder_id: Optional[UUID] = None,
    descendant_of: Optional[UUID] = None
) -> Optional[Asset]:
    """
    Create a new asset from an uploaded file.
    
    Args:
        db: Database session
        name: Original filename
        temp_file_path: Path to temporary uploaded file
        created_by: User uploading the asset
        folder_id: Parent folder ID (None for root)
        descendant_of: Parent asset ID if this is a transformation
        
    Returns:
        Asset object if created successfully
        
    Raises:
        ValueError: If folder not found
        ValueError: If file size exceeds limit
        IOError: If file operations fail
    """
    # Validate folder if specified
    if folder_id:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            raise ValueError("Parent folder not found")
    
    # Get file size and validate
    try:
        file_size = os.path.getsize(temp_file_path)
    except OSError as e:
        raise IOError(f"Could not read uploaded file: {e}")

    is_valid, error = validate_file_size(file_size)
    if not is_valid:
        raise ValueError(error)

    # Generate ID and storage filename before creating the record
    mime_type = get_mime_type(name)
    asset_id = uuid4()
    storage_filename = generate_storage_filename(asset_id, name)

    asset = Asset(
        id=asset_id,
        name=name,
        storage_filename=storage_filename,
        mime_type=mime_type,
        size_bytes=file_size,
        folder_id=folder_id,
        descendant_of=descendant_of,
        created_by_id=created_by.id if created_by else None,
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    # Move file from temp to assets directory
    save_uploaded_file(temp_file_path, asset.storage_filename)

    return asset
