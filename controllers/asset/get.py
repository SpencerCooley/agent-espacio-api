"""
Asset controller - get asset.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.asset import Asset


def get_asset(db: Session, asset_id: UUID) -> Optional[Asset]:
    """
    Get an asset by ID.
    
    Args:
        db: Database session
        asset_id: Asset UUID
        
    Returns:
        Asset object if found, None otherwise
    """
    return db.query(Asset).filter(Asset.id == asset_id).first()


def get_asset_by_storage_filename(db: Session, storage_filename: str) -> Optional[Asset]:
    """
    Get an asset by its storage filename.
    
    Useful for correlating files on disk with database records.
    
    Args:
        db: Database session
        storage_filename: The storage filename (e.g., "uuid_filename.png")
        
    Returns:
        Asset object if found, None otherwise
    """
    return db.query(Asset).filter(Asset.storage_filename == storage_filename).first()
