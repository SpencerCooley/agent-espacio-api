"""
Folder controller - create folder.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.folder import Folder
from models.user import User


def create_folder(
    db: Session,
    name: str,
    created_by: User,
    parent_id: Optional[UUID] = None
) -> Optional[Folder]:
    """
    Create a new folder.
    
    Args:
        db: Database session
        name: Folder name
        created_by: User creating the folder
        parent_id: Parent folder ID (None for root level)
        
    Returns:
        Folder object if created successfully, None if parent not found
        
    Raises:
        ValueError: If trying to create a subfolder under the root incorrectly
    """
    # Validate parent folder if specified
    parent = None
    if parent_id:
        parent = db.query(Folder).filter(Folder.id == parent_id).first()
        if not parent:
            return None
    
    # Create folder
    folder = Folder(
        name=name,
        parent_id=parent_id,
        is_root=False,  # Only system creates root folder
        created_by_id=created_by.id
    )
    
    # Build the materialized path
    folder.build_path()
    
    db.add(folder)
    db.commit()
    db.refresh(folder)
    
    return folder
