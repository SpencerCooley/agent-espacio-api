"""
Assets router.

Endpoints for asset (file) management:
- GET /assets - List assets with optional filters
- POST /assets/upload - Upload a file
- GET /assets/{asset_id} - Get asset metadata
- PUT /assets/{asset_id} - Update asset (rename or move)
- GET /assets/{asset_id}/download - Download/stream the file (supports range requests)
- DELETE /assets/{asset_id} - Delete asset
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy.orm import Session
from uuid import UUID

from dependencies.dependencies import get_db, require_auth
from models.user import User
from types_definitions.asset import (
    AssetResponse,
    AssetListResponse,
    DeleteAssetResponse,
    AssetUploadResponse,
    UpdateAssetRequest,
)
from services.file_storage import (
    get_temp_path,
    save_uploaded_file,
    read_file,
    read_file_from_path,
    read_file_range,
    read_text_file,
    get_thumbnail_path,
    thumbnail_exists,
    THUMBNAIL_SIZES,
    MAX_FILE_SIZE,
)
from utils.range_request import create_streaming_response_with_range
import controllers
import os
import shutil
from services.events import publish_event

router = APIRouter(
    prefix="/assets",
    tags=["Assets"],
    responses={404: {"description": "Not found"}}
)


@router.get("", response_model=AssetListResponse)
async def list_assets(
    folder_id: UUID = None,
    mime_type: str = None,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    List assets with optional filters.
    
    - **folder_id**: Filter by parent folder
    - **mime_type**: Filter by MIME type (e.g., "image/" for all images)
    """
    assets = controllers.asset.list_assets(
        db=db,
        folder_id=folder_id,
        mime_type_prefix=mime_type
    )
    
    return AssetListResponse(assets=assets, total=len(assets))


@router.post("/upload", response_model=AssetUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(..., description="File to upload"),
    folder_id: UUID = Form(None, description="Parent folder ID (optional)"),
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Upload a new file as an asset.
    
    - **file**: The file to upload (max 50MB)
    - **folder_id**: Optional parent folder ID (omit for root/My Drive)
    
    Supported file types: Images (.png, .jpg, .gif), Markdown (.md), and more.
    """
    # Validate file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {actual_mb:.1f}MB exceeds maximum allowed size of {max_mb:.0f}MB"
        )
    
    # Create temp file path
    temp_path = get_temp_path(file.filename)
    
    try:
        # Save uploaded file to temp location
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create asset record and move file to storage
        asset = controllers.asset.create_asset(
            db=db,
            name=file.filename,
            temp_file_path=temp_path,
            created_by=current_user,
            folder_id=folder_id
        )
        
        actor = {"type": "user", "id": str(current_user.id) if current_user else None, "name": current_user.email if current_user else None}
        parent_id = str(folder_id) if folder_id else "00000000-0000-0000-0000-000000000001"
        publish_event(
            event_type="asset.created",
            folder_id=parent_id,
            resource_id=str(asset.id),
            payload={"name": asset.name, "mime_type": asset.mime_type},
            actor=actor,
        )
        publish_event(
            event_type="folder_contents_changed",
            folder_id=parent_id,
            resource_id=str(asset.id),
            payload={"name": asset.name},
            actor=actor,
        )
        
        return AssetUploadResponse(asset=asset)
        
    except ValueError as e:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )
    finally:
        file.file.close()


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get asset metadata by ID.
    """
    asset = controllers.asset.get_asset(db, asset_id)
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    
    return asset


def _serve_asset_file(asset, request: Request, size: int = None):
    """Serve an asset file (thumbnail or original with range support)."""
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

    # Stream the original file with range request support
    from services.file_storage import get_asset_path
    file_path = get_asset_path(asset.storage_filename)

    try:
        return create_streaming_response_with_range(
            file_path=file_path,
            request=request,
            media_type=asset.mime_type,
            filename=asset.name,
            read_file_func=lambda chunk_size: read_file(asset.storage_filename, chunk_size),
            read_range_func=lambda start, end, chunk_size: read_file_range(asset.storage_filename, start, end, chunk_size),
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )


@router.post("/{asset_id}/signed-url")
async def create_signed_url(
    asset_id: UUID,
    size: int = None,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Generate a time-bound signed URL for downloading an asset.

    The signed URL is valid for 10 minutes and can be used without authentication.
    """
    asset = controllers.asset.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    from controllers.asset.signed_url import generate_signed_url
    signed_url = generate_signed_url(asset_id, size=size)

    return {"signed_url": signed_url}


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: UUID,
    request: Request,
    size: int = None,
    signed: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Download or stream the file for an asset.

    Supports two authentication modes:
    1. **Signed URL**: Pass `?signed=` query param for time-bound unauthenticated access.
    2. **Bearer token / API key**: Standard authentication via Authorization header or X-Agent-Key.

    Supports HTTP Range requests for video/audio streaming.
    """
    asset = controllers.asset.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    # Mode 1: Signed URL (unauthenticated, time-bound)
    if signed:
        from controllers.asset.signed_url import verify_signed_url
        if verify_signed_url(signed, asset_id, size):
            return _serve_asset_file(asset, request, size)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired signed URL")

    # Mode 2: Normal authentication
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    x_agent_key = request.headers.get("X-Agent-Key")

    from dependencies.dependencies import _validate_auth
    user = _validate_auth(db, token or None, x_agent_key or None)

    if user is None and not x_agent_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer, X-Agent-Key"}
        )

    return _serve_asset_file(asset, request, size)


@router.get("/{asset_id}/content")
async def get_asset_content(
    asset_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get the text content of an asset.
    
    Returns the raw file content as plain text. Intended for text-based files
    like markdown, text files, etc.
    """
    asset = controllers.asset.get_asset(db, asset_id)

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    try:
        content = read_text_file(asset.storage_filename)
        return PlainTextResponse(content, media_type=asset.mime_type)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: UUID,
    request: UpdateAssetRequest,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Update an asset (rename or move to a different folder).
    
    - **name**: New filename (optional)
    - **folder_id**: New parent folder ID (optional, for moving)
    """
    asset = controllers.asset.get_asset(db, asset_id)
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    
    try:
        original_folder_id = str(asset.folder_id) if asset.folder_id else "00000000-0000-0000-0000-000000000001"
        updated = controllers.asset.update_asset(
            db=db,
            asset=asset,
            name=request.name,
            folder_id=request.folder_id,
            content=request.content,
        )
        new_folder_id = str(updated.folder_id) if updated.folder_id else "00000000-0000-0000-0000-000000000001"
        
        # Emit move event if folder changed
        if request.folder_id is not None and new_folder_id != original_folder_id:
            actor = {"type": "user", "id": str(current_user.id) if current_user else None, "name": current_user.email if current_user else None}
            publish_event(
                event_type="asset.moved",
                folder_id=new_folder_id,
                resource_id=str(asset_id),
                payload={"name": updated.name, "source_folder_id": original_folder_id},
                actor=actor,
            )
        
        return updated
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{asset_id}", response_model=DeleteAssetResponse)
async def delete_asset(
    asset_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Delete an asset and its file from storage.
    
    This action cannot be undone.
    """
    asset = controllers.asset.get_asset(db, asset_id)
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    
    folder_id = str(asset.folder_id) if asset.folder_id else "00000000-0000-0000-0000-000000000001"
    file_deleted = controllers.asset.delete_asset(db, asset)
    
    actor = {"type": "user", "id": str(current_user.id) if current_user else None, "name": current_user.email if current_user else None}
    publish_event(
        event_type="asset.deleted",
        folder_id=folder_id,
        resource_id=str(asset_id),
        payload={"name": asset.name},
        actor=actor,
    )
    publish_event(
        event_type="folder_contents_changed",
        folder_id=folder_id,
        resource_id=str(asset_id),
        payload={"name": asset.name},
        actor=actor,
    )
    
    return DeleteAssetResponse(
        deleted_asset_id=asset_id,
        deleted_file=file_deleted
    )


@router.post("/{asset_id}/share", response_model=AssetResponse)
async def share_asset(
    asset_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Toggle public sharing for an asset.
    
    Generates a public_magic_id when making public, clears it when making private.
    """
    asset = controllers.asset.get_asset(db, asset_id)
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    
    updated = controllers.asset.share.toggle_asset_share(db, asset)
    return updated
