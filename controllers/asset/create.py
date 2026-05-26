"""
Asset controller - create asset.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.asset import Asset
from models.folder import Folder
from models.user import User
from services.file_storage import (
    get_mime_type,
    generate_storage_filename,
    save_uploaded_file,
    get_file_size,
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
    file_size = get_file_size(temp_file_path)
    if file_size is None:
        raise IOError("Could not read uploaded file")
    
    is_valid, error = validate_file_size(file_size)
    if not is_valid:
        raise ValueError(error)
    
    # Create asset record first (to get the ID)
    mime_type = get_mime_type(name)
    
    asset = Asset(
        name=name,
        mime_type=mime_type,
        size_bytes=file_size,
        folder_id=folder_id,
        descendant_of=descendant_of,
        created_by_id=created_by.id
    )
    
    db.add(asset)
    db.flush()  # Get the ID without committing
    
    # Generate storage filename with asset ID
    asset.storage_filename = generate_storage_filename(asset.id, name)
    
    # Move file from temp to assets directory
    save_uploaded_file(temp_file_path, asset.storage_filename)
    
    db.commit()
    db.refresh(asset)
    
    return asset
