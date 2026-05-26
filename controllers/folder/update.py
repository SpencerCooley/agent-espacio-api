"""
Folder controller - update folder.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.folder import Folder


def update_folder(
    db: Session,
    folder: Folder,
    name: Optional[str] = None,
    parent_id: Optional[UUID] = None
) -> Folder:
    """
    Update a folder's name or move it to a different parent.
    
    Args:
        db: Database session
        folder: Folder object to update
        name: New folder name
        parent_id: New parent folder ID (for moving)
        
    Returns:
        Updated folder object
        
    Raises:
        ValueError: If trying to move folder to make it a child of itself
        ValueError: If trying to move the root folder
        ValueError: If new parent not found
    """
    # Prevent moving root folder
    if folder.is_root and parent_id is not None:
        raise ValueError("Cannot move the root folder")
    
    # Update name if provided
    if name and name != folder.name:
        folder.name = name
    
    # Move folder if parent_id provided and different
    if parent_id is not None and parent_id != folder.parent_id:
        # Can't move folder to be its own child
        if parent_id == folder.id:
            raise ValueError("Cannot move a folder into itself")
        
        # Check for circular reference (can't move into a descendant)
        if _is_descendant(db, folder.id, parent_id):
            raise ValueError("Cannot move a folder into one of its subfolders")
        
        # Validate new parent exists
        new_parent = db.query(Folder).filter(Folder.id == parent_id).first()
        if not new_parent:
            raise ValueError("Parent folder not found")
        
        folder.parent_id = parent_id
    
    # Recalculate path
    folder.build_path()
    
    # Update children paths recursively
    _update_children_paths(db, folder)
    
    db.commit()
    db.refresh(folder)
    
    return folder


def _is_descendant(db: Session, ancestor_id: UUID, potential_descendant_id: UUID) -> bool:
    """
    Check if potential_descendant_id is actually a descendant of ancestor_id.
    
    Used to prevent circular folder references when moving.
    """
    current = db.query(Folder).filter(Folder.id == potential_descendant_id).first()
    
    while current and current.parent_id:
        if current.parent_id == ancestor_id:
            return True
        current = db.query(Folder).filter(Folder.id == current.parent_id).first()
    
    return False


def _update_children_paths(db: Session, folder: Folder):
    """
    Recursively update the path of all child folders.
    
    Called when a folder is moved or renamed.
    """
    children = db.query(Folder).filter(Folder.parent_id == folder.id).all()
    
    for child in children:
        child.build_path()
        _update_children_paths(db, child)  # Recurse into grandchildren
