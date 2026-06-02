"""
Folder controller - delete folder.
"""
from uuid import UUID
from typing import Tuple

from sqlalchemy.orm import Session

from models.folder import Folder
from services.file_storage import delete_file


def delete_folder(
    db: Session,
    folder: Folder
) -> Tuple[int, int]:
    """
    Delete a folder and ALL its contents recursively.
    
    This includes:
    - All subfolders (recursively)
    - All assets in the folder and subfolders
    - All artifacts in the folder and subfolders
    - All asset files from disk storage
    
    Args:
        db: Database session
        folder: Folder object to delete
        
    Returns:
        Tuple of (deleted_subfolders_count, deleted_assets_count)
        
    Raises:
        ValueError: If trying to delete the root folder
    """
    if folder.is_root:
        raise ValueError("Cannot delete the root folder (My Drive)")
    
    # Recursively delete all contents and count
    subfolders_count, assets_count = _delete_folder_recursive(db, folder)
    
    # Delete the folder itself from database
    db.delete(folder)
    db.commit()
    
    return subfolders_count, assets_count


def _delete_folder_recursive(
    db: Session,
    folder: Folder
) -> Tuple[int, int]:
    """
    Recursively delete a folder's contents (subfolders, assets, and artifacts).
    
    Returns counts of deleted items (not including the folder itself).
    """
    subfolders_count = 0
    assets_count = 0
    
    # First, recursively delete all subfolders
    for child in list(folder.children):
        child_subfolders, child_assets = _delete_folder_recursive(db, child)
        subfolders_count += child_subfolders
        assets_count += child_assets
        
        # Delete the child folder itself
        db.delete(child)
        subfolders_count += 1
    
    # Delete all assets in this folder
    for asset in list(folder.assets):
        # Delete the file from disk
        delete_file(asset.storage_filename)
        
        # Delete from database
        db.delete(asset)
        assets_count += 1
    
    # Delete all artifacts in this folder (explicitly, for safety)
    for artifact in list(folder.artifacts):
        db.delete(artifact)
    
    return subfolders_count, assets_count
