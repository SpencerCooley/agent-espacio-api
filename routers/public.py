"""
Public view router.

Unauthenticated endpoints for viewing publicly shared content:
- GET /public/view/{magic_id} - View a public folder, asset, or artifact
- GET /public/assets/{magic_id}/download - Download/stream a public asset (supports range requests)
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db
from types_definitions.folder import FolderResponse, FolderContentsResponse
from types_definitions.artifact import FolderItemResponse
from types_definitions.asset import AssetResponse
from types_definitions.artifact import ArtifactResponse, CompositionResponse, CompositionSectionResponse
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
from controllers.themes import get_public_theme_definition

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
    
    # Resolve public theme with full definition
    public_theme_pref = get_public_theme(db)
    public_theme_definition = get_public_theme_definition(
        db, public_theme_pref['theme_id'], public_theme_pref['mode']
    ) if public_theme_pref['theme_id'] else None
    public_theme_response = {
        "theme_id": public_theme_pref['theme_id'],
        "mode": public_theme_pref['mode'],
        "definition": public_theme_definition,
    }

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
                "inherited_public": not f.is_public,
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
                "is_public": a.is_public,
                "inherited_public": not a.is_public,
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
                "is_public": art.is_public,
                "inherited_public": not art.is_public,
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
            "public_theme": public_theme_response,
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
            "public_theme": public_theme_response,
        }

    elif kind == 'artifact':
        import copy
        from controllers.asset.signed_url import enrich_content_with_signed_urls
        enriched_content = enrich_content_with_signed_urls(
            copy.deepcopy(item.content or {}), expiry_seconds=3600
        )
        return {
            "kind": "artifact",
            "artifact": {
                "id": item.id,
                "name": item.name,
                "type": item.type,
                "description": item.description,
                "content": enriched_content,
                "is_public": True,
                "public_magic_id": item.public_magic_id,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            },
            "public_theme": public_theme_response,
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


@router.get("/search/{magic_id}")
async def public_folder_search(
    magic_id: UUID,
    q: str,
    db: Session = Depends(get_db)
):
    """
    Search for items by name within a public folder and all its subfolders.

    Only returns items that are publicly accessible.

    Query param:
        q: Search term

    Returns a unified list of matching items in the same shape as folder contents.
    """
    item, kind = controllers.public.resolve_public_item(db, magic_id)

    if not item or kind != 'folder':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public folder not found"
        )

    if not controllers.public.is_folder_public(db, item):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder is not publicly accessible"
        )

    if not q or not q.strip():
        return {
            "kind": "folder",
            "folder": {
                "id": item.id,
                "name": item.name,
                "is_public": item.is_public,
                "public_magic_id": item.public_magic_id,
            },
            "items": [],
            "total_items": 0,
        }

    folders_result, assets_result, artifacts_result = controllers.public.search_public_folder_scope(
        db, item, q.strip()
    )

    items = []

    for f in folders_result:
        items.append(FolderItemResponse(
            kind="folder",
            id=f.id,
            name=f.name,
            type=None,
            mime_type=None,
            size_bytes=None,
            is_image=None,
            is_public=f.is_public,
            inherited_public=not f.is_public,
            public_magic_id=f.public_magic_id,
            created_at=f.created_at,
            updated_at=f.updated_at,
        ))

    for a in assets_result:
        items.append(FolderItemResponse(
            kind="asset",
            id=a.id,
            name=a.name,
            type=None,
            mime_type=a.mime_type,
            size_bytes=a.size_bytes,
            is_image=a.is_image,
            file_meta=a.file_meta,
            is_public=a.is_public,
            inherited_public=not a.is_public,
            public_magic_id=a.public_magic_id,
            created_at=a.created_at,
            updated_at=a.updated_at,
        ))

    for ar in artifacts_result:
        items.append(FolderItemResponse(
            kind="artifact",
            id=ar.id,
            name=ar.name,
            type=ar.type,
            mime_type=None,
            size_bytes=None,
            is_image=None,
            is_public=ar.is_public,
            inherited_public=not ar.is_public,
            public_magic_id=ar.public_magic_id,
            created_at=ar.created_at,
            updated_at=ar.updated_at,
        ))

    items.sort(key=lambda x: x.name.lower())

    return {
        "kind": "folder",
        "folder": {
            "id": item.id,
            "name": item.name,
            "is_public": item.is_public,
            "public_magic_id": item.public_magic_id,
        },
        "items": items,
        "total_items": len(items),
    }


@router.get("/composition/{magic_id}")
async def public_composition(
    magic_id: UUID,
    db: Session = Depends(get_db)
):
    """
    View a public composer artifact with all resolved sub-artifacts.

    Only sub-artifacts that are publicly accessible are included.
    Private sub-artifacts appear as null in their section.
    """
    item, kind = controllers.public.resolve_public_item(db, magic_id)

    if not item or kind != 'artifact':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public composition not found"
        )

    if item.type != "composer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact is not a composition"
        )

    # Resolve public theme
    public_theme_pref = get_public_theme(db)
    public_theme_definition = get_public_theme_definition(
        db, public_theme_pref['theme_id'], public_theme_pref['mode']
    ) if public_theme_pref['theme_id'] else None
    public_theme_response = {
        "theme_id": public_theme_pref['theme_id'],
        "mode": public_theme_pref['mode'],
        "definition": public_theme_definition,
    }

    # Resolve composition (filters non-public sub-artifacts)
    result = controllers.artifact.resolve_public_composition(db, item)

    return {
        "kind": "composition",
        "composer": result["composer"],
        "sections": [
            {
                "artifact": s["item"],
                "caption": s["caption"],
                "artifact_id": s["artifact_id"],
            }
            for s in result["sections"]
        ],
        "public_theme": public_theme_response,
    }
