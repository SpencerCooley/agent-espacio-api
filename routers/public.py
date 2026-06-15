"""
Public view router.

Unauthenticated endpoints for viewing publicly shared content:
- GET /public/view/{magic_id} - View a public folder, asset, or artifact
- GET /public/assets/{magic_id}/download - Download a public asset
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db
from types_definitions.folder import FolderResponse, FolderContentsResponse
from types_definitions.asset import AssetResponse
from types_definitions.artifact import ArtifactResponse
import controllers
from models.asset import Asset
from models.folder import Folder
from services.file_storage import get_asset_path
from controllers.settings import get_public_theme

router = APIRouter(
    prefix="/public",
    tags=["Public"],
    responses={404: {"description": "Not found"}}
)


@router.get("/view/{magic_id}")
async def public_view(
    magic_id: UUID,
    db: Session = Depends(get_db)
):
    """
    View a publicly shared item by its magic_id.
    
    Returns the item details with a 'kind' field indicating the type.
    
    - **Folder**: Returns folder details with its public contents
    - **Asset**: Returns asset metadata
    - **Artifact**: Returns artifact metadata
    """
    item, kind = controllers.public.resolve_public_item(db, magic_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public item not found"
        )
    
    if kind == 'folder':
        subfolders, assets, artifacts = controllers.public.get_public_folder_contents(db, item)
        
        # Build ancestor chain for breadcrumb
        ancestors = []
        current = item
        while current.parent_id:
            parent = db.query(Folder).filter(Folder.id == current.parent_id).first()
            if not parent:
                break
            ancestors.insert(0, {
                "id": str(parent.id),
                "name": parent.name,
                "is_public": parent.is_public,
                "public_magic_id": str(parent.public_magic_id) if parent.public_magic_id else None,
            })
            current = parent
        
        # Convert to response schemas
        folder_items = []
        for f in subfolders:
            folder_items.append({
                "kind": "folder",
                "id": f.id,
                "name": f.name,
                "is_public": f.is_public,
                "public_magic_id": f.public_magic_id,
                "created_at": f.created_at,
                "updated_at": f.updated_at,
            })
        for a in assets:
            folder_items.append({
                "kind": "asset",
                "id": a.id,
                "name": a.name,
                "mime_type": a.mime_type,
                "is_image": a.is_image,
                "is_public": a.is_public or (item.is_public if item else False),
                "public_magic_id": a.public_magic_id,
                "created_at": a.created_at,
                "updated_at": a.updated_at,
            })
        for art in artifacts:
            folder_items.append({
                "kind": "artifact",
                "id": art.id,
                "name": art.name,
                "type": art.type,
                "is_public": art.is_public or (item.is_public if item else False),
                "public_magic_id": art.public_magic_id,
                "created_at": art.created_at,
                "updated_at": art.updated_at,
            })
        
        return {
            "kind": "folder",
            "folder": {
                "id": item.id,
                "name": item.name,
                "path": item.path,
                "parent_id": str(item.parent_id) if item.parent_id else None,
                "is_public": item.is_public,
                "public_magic_id": item.public_magic_id,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            },
            "ancestors": ancestors,
            "items": folder_items,
            "total_items": len(folder_items),
            "public_theme": get_public_theme(db)
        }
    
    elif kind == 'asset':
        return {
            "kind": "asset",
            "asset": {
                "id": item.id,
                "name": item.name,
                "mime_type": item.mime_type,
                "size_bytes": item.size_bytes,
                "human_readable_size": item.human_readable_size,
                "is_image": item.is_image,
                "is_public": True,
                "public_magic_id": item.public_magic_id,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            },
            "public_theme": get_public_theme(db)
        }
    
    elif kind == 'artifact':
        return {
            "kind": "artifact",
            "artifact": {
                "id": item.id,
                "name": item.name,
                "type": item.type,
                "description": item.description,
                "content": item.content,
                "is_public": True,
                "public_magic_id": item.public_magic_id,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            },
            "public_theme": get_public_theme(db)
        }
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Unknown item type"
    )


@router.get("/assets/{magic_id}/download")
async def public_download_asset(
    magic_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Download a publicly shared asset by its magic_id.
    
    Also supports derived access for assets linked from public artifacts.
    """
    # First try direct public magic_id
    asset = db.query(Asset).filter(
        Asset.public_magic_id == magic_id
    ).first()
    
    if not asset:
        # Check if it's an asset ID that has derived access
        try:
            asset_id = magic_id
            asset = controllers.asset.get_asset(db, asset_id)
            if asset and not controllers.public.is_asset_public(db, asset):
                asset = None
        except:
            asset = None
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public asset not found"
        )
    
    if not controllers.public.is_asset_public(db, asset):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset is not publicly accessible"
        )
    
    file_path = get_asset_path(asset.storage_filename)
    
    return FileResponse(
        path=file_path,
        filename=asset.name,
        media_type=asset.mime_type
    )
