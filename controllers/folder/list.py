"""
Folder controller - list folders.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.folder import Folder


def list_folders(
    db: Session,
    parent_id: Optional[UUID] = None,
    include_root: bool = True
) -> List[Folder]:
    """
    List folders, optionally filtered by parent.
    
    Args:
        db: Database session
        parent_id: Filter by parent folder (None for root-level folders)
        include_root: Whether to include the system root folder
        
    Returns:
        List of Folder objects
    """
    query = db.query(Folder)
    
    if not include_root:
        query = query.filter(Folder.is_root == False)
    
    if parent_id is not None:
        query = query.filter(Folder.parent_id == parent_id)
    
    # Order alphabetically by name
    return query.order_by(Folder.name).all()


def get_folder_tree(
    db: Session,
    root_folder_id: Optional[UUID] = None
) -> List[Folder]:
    """
    Get folder tree starting from a root folder.
    
    Args:
        db: Database session
        root_folder_id: Starting folder (None for full tree from My Drive)
        
    Returns:
        List of top-level folders with children loaded
    """
    query = db.query(Folder)
    
    if root_folder_id:
        # Get specific folder and its descendants
        query = query.filter(
            (Folder.id == root_folder_id) | (Folder.path.like(f"%{root_folder_id}%"))
        )
    else:
        # Get all folders except root, we'll construct tree separately
        query = query.filter(Folder.is_root == False)
    
    return query.order_by(Folder.path).all()


def count_folders_in_parent(db: Session, parent_id: Optional[UUID] = None) -> int:
    """
    Count folders in a specific parent (or root-level folders).
    
    Args:
        db: Database session
        parent_id: Parent folder ID (None for root level)
        
    Returns:
        Number of folders
    """
    query = db.query(Folder)
    
    if parent_id is not None:
        query = query.filter(Folder.parent_id == parent_id)
    else:
        query = query.filter(Folder.parent_id.is_(None), Folder.is_root == False)
    
    return query.count()


def get_folder_contents(
    db: Session,
    folder_id: UUID
) -> tuple[List[Folder], List, List]:
    """
    Get immediate subfolders, assets, and artifacts in a folder.
    
    Args:
        db: Database session
        folder_id: Folder ID to get contents for
        
    Returns:
        Tuple of (subfolders list, assets list, artifacts list)
    """
    subfolders = db.query(Folder).filter(Folder.parent_id == folder_id).order_by(Folder.name).all()
    
    # Import here to avoid circular imports
    from models.asset import Asset
    assets = db.query(Asset).filter(Asset.folder_id == folder_id).order_by(Asset.name).all()
    
    from models.artifact import Artifact
    artifacts = db.query(Artifact).filter(Artifact.folder_id == folder_id).order_by(Artifact.name).all()
    
    return subfolders, assets, artifacts
