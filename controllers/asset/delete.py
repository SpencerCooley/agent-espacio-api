"""
Asset controller - delete asset.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from models.asset import Asset
from services.file_storage import delete_file


def delete_asset(
    db: Session,
    asset: Asset
) -> bool:
    """
    Delete an asset and its file from storage.
    
    Args:
        db: Database session
        asset: Asset object to delete
        
    Returns:
        True if file was successfully deleted from disk
        
    Note:
        Database record is always deleted.
        File deletion is attempted but failures are logged, not raised.
    """
    # Delete the file from disk
    file_deleted = delete_file(asset.storage_filename)
    
    # Delete the database record
    db.delete(asset)
    db.commit()
    
    return file_deleted


def delete_assets_by_folder(
    db: Session,
    folder_id: UUID
) -> int:
    """
    Delete all assets in a folder.
    
    Used during recursive folder deletion.
    
    Args:
        db: Database session
        folder_id: Folder ID whose assets to delete
        
    Returns:
        Number of assets deleted
    """
    assets = db.query(Asset).filter(Asset.folder_id == folder_id).all()
    
    count = 0
    for asset in assets:
        delete_file(asset.storage_filename)
        db.delete(asset)
        count += 1
    
    db.commit()
    return count
