"""
Public view router.

Unauthenticated endpoints for viewing publicly shared content:
- GET /public/view/{magic_id} - View a public folder, asset, or artifact
- GET /public/assets/{magic_id}/download - Download/stream a public asset (supports range requests)
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db
from types_definitions.folder import FolderResponse, FolderContentsResponse
from types_definitions.asset import AssetResponse
from types_definitions.artifact import ArtifactResponse
import controllers
from models.asset import Asset
from models.folder import Folder
from services.file_storage import (
    get_asset_path,
    get_thumbnail_path,
    thumbnail_exists,
    read_file_from_path,
    read_file_range_from_path,
    THUMBNAIL_SIZES,
)
from utils.range_request import create_streaming_response_with_range
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
                "id": str(f.id),
                "name": f.name,
                "is_public": f.is_public,
                "public_magic_id": str(f.public_magic_id) if f.public_magic_id else None,
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
    request: Request,
    size: int = None,
    db: Session = Depends(get_db)
):
    """
    Download or stream a publicly shared asset by its magic_id.
    
    Supports HTTP Range requests for video/audio streaming, allowing players
    to seek to arbitrary positions without downloading the entire file first.
    
    Also supports derived access for assets linked from public artifacts.
    
    - **size**: Optional thumbnail size (e.g., 256, 512). Only available for image
      and video assets. Falls back to original for images if thumbnail not generated.
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
    
    # Thumbnail download
    if size is not None:
        if size not in THUMBNAIL_SIZES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid thumbnail size. Supported sizes: {THUMBNAIL_SIZES}"
            )
        if not asset.is_image and not asset.mime_type.startswith("video/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thumbnails are only available for image and video assets"
            )
        if not thumbnail_exists(asset.id, size):
            if asset.mime_type.startswith("video/"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Video thumbnail not found"
                )
            # Fall back to original for images
            pass
        else:
            try:
                return StreamingResponse(
                    read_file_from_path(get_thumbnail_path(asset.id, size)),
                    media_type="image/webp",
                    headers={
                        "Content-Disposition": f'inline; filename="{asset.id}_thumb_{size}.webp"',
                        "Accept-Ranges": "bytes",
                    }
                )
            except FileNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Thumbnail file not found on disk"
                )
    
    file_path = get_asset_path(asset.storage_filename)
    
    # Use streaming response with range request support for video/audio streaming
    return create_streaming_response_with_range(
        file_path=file_path,
        request=request,
        media_type=asset.mime_type,
        filename=asset.name,
        read_file_func=lambda chunk_size: read_file_from_path(file_path, chunk_size),
        read_range_func=lambda start, end, chunk_size: read_file_range_from_path(file_path, start, end, chunk_size),
    )
