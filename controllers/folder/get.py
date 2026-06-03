"""
Folder controller - get folder.
"""
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

from models.folder import Folder


def get_folder(db: Session, folder_id: UUID) -> Optional[Folder]:
    """
    Get a folder by ID.
    
    Args:
        db: Database session
        folder_id: Folder UUID
        
    Returns:
        Folder object if found, None otherwise
    """
    return db.query(Folder).filter(Folder.id == folder_id).first()


def get_root_folder(db: Session) -> Optional[Folder]:
    """
    Get the system root folder ("My Drive").
    
    Args:
        db: Database session
        
    Returns:
        Root folder object if found, None otherwise
    """
    return db.query(Folder).filter(Folder.is_root == True).first()


def get_folder_by_path(db: Session, path: str) -> Optional[Folder]:
    """
    Get a folder by its materialized path.
    
    Args:
        db: Database session
        path: Folder path (e.g., "/My Drive/Documents/")
        
    Returns:
        Folder object if found, None otherwise
    """
    return db.query(Folder).filter(Folder.path == path).first()


def get_folder_ancestors(db: Session, folder_id: UUID) -> List[Folder]:
    """
    Get the ancestor chain for a folder, from root to the folder itself.
    
    Walks up the parent_id chain to build the full path.
    
    Args:
        db: Database session
        folder_id: Folder UUID
        
    Returns:
        List of Folder objects in order from root to the given folder
    """
    folder = get_folder(db, folder_id)
    if not folder:
        return []
    
    ancestors = []
    current = folder
    while current:
        ancestors.append(current)
        if current.parent_id:
            current = get_folder(db, current.parent_id)
        else:
            current = None
    
    ancestors.reverse()
    return ancestors
