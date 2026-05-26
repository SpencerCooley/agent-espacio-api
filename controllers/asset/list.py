"""
Asset controller - list assets.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.asset import Asset


def list_assets(
    db: Session,
    folder_id: Optional[UUID] = None,
    mime_type_prefix: Optional[str] = None,
    descendant_of: Optional[UUID] = None,
    created_by_id: Optional[int] = None
) -> List[Asset]:
    """
    List assets with optional filters.
    
    Args:
        db: Database session
        folder_id: Filter by parent folder (None for root-level or loose assets)
        mime_type_prefix: Filter by MIME type prefix (e.g., "image/" for all images)
        descendant_of: Filter by parent asset (for transformations)
        created_by_id: Filter by uploader user ID
        
    Returns:
        List of Asset objects
    """
    query = db.query(Asset)
    
    if folder_id is not None:
        query = query.filter(Asset.folder_id == folder_id)
    
    if mime_type_prefix:
        query = query.filter(Asset.mime_type.like(f"{mime_type_prefix}%"))
    
    if descendant_of:
        query = query.filter(Asset.descendant_of == descendant_of)
    
    if created_by_id:
        query = query.filter(Asset.created_by_id == created_by_id)
    
    # Order by creation date, newest first
    return query.order_by(Asset.created_at.desc()).all()


def count_assets_in_folder(db: Session, folder_id: Optional[UUID] = None) -> int:
    """
    Count assets in a specific folder (or root-level assets).
    
    Args:
        db: Database session
        folder_id: Folder ID (None for root level)
        
    Returns:
        Number of assets
    """
    query = db.query(Asset)
    
    if folder_id is not None:
        query = query.filter(Asset.folder_id == folder_id)
    else:
        query = query.filter(Asset.folder_id.is_(None))
    
    return query.count()


def get_image_assets(db: Session, folder_id: Optional[UUID] = None) -> List[Asset]:
    """
    Get all image assets, optionally filtered by folder.
    
    Args:
        db: Database session
        folder_id: Optional folder filter
        
    Returns:
        List of image Asset objects
    """
    query = db.query(Asset).filter(Asset.mime_type.like("image/%"))
    
    if folder_id is not None:
        query = query.filter(Asset.folder_id == folder_id)
    
    return query.order_by(Asset.created_at.desc()).all()


def get_descendants(db: Session, parent_asset_id: UUID) -> List[Asset]:
    """
    Get all descendant assets (transformations) of a parent asset.
    
    Args:
        db: Database session
        parent_asset_id: Parent asset ID
        
    Returns:
        List of descendant Asset objects
    """
    return db.query(Asset).filter(
        Asset.descendant_of == parent_asset_id
    ).order_by(Asset.created_at.desc()).all()
