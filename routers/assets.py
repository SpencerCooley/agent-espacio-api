"""
Assets router.

Endpoints for asset (file) management:
- GET /assets - List assets with optional filters
- POST /assets/upload - Upload a file
- GET /assets/{asset_id} - Get asset metadata
- PUT /assets/{asset_id} - Update asset (rename or move)
- GET /assets/{asset_id}/download - Download the file
- DELETE /assets/{asset_id} - Delete asset
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
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
    read_text_file,
    get_thumbnail_path,
    thumbnail_exists,
    THUMBNAIL_SIZES,
    MAX_FILE_SIZE,
)
import controllers
import os
import shutil

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


@router.get("/{asset_id}/download")
async def download_asset(
    asset_id: UUID,
    size: int = None,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Download the file for an asset.
    
    - **size**: Optional thumbnail size (e.g., 256, 512). Only available for image assets.
      Falls back to original if the requested thumbnail size wasn't generated.
    
    Returns the file with appropriate content type headers.
    """
    asset = controllers.asset.get_asset(db, asset_id)
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    
    # Thumbnail download
    if size is not None:
        if size not in THUMBNAIL_SIZES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid thumbnail size. Supported sizes: {THUMBNAIL_SIZES}"
            )
        if not asset.is_image:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thumbnails are only available for image assets"
            )
        if not thumbnail_exists(asset_id, size):
            # Fall back to original if thumbnail wasn't generated (e.g., image was smaller than size)
            pass
        else:
            try:
                return StreamingResponse(
                    read_file_from_path(get_thumbnail_path(asset_id, size)),
                    media_type="image/webp",
                    headers={
                        "Content-Disposition": f'inline; filename="{asset_id}_thumb_{size}.webp"'
                    }
                )
            except FileNotFoundError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Thumbnail file not found on disk"
                )
    
    try:
        # Stream the original file
        return StreamingResponse(
            read_file(asset.storage_filename),
            media_type=asset.mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{asset.name}"'
            }
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )


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
        updated = controllers.asset.update_asset(
            db=db,
            asset=asset,
            name=request.name,
            folder_id=request.folder_id,
            content=request.content,
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
    
    file_deleted = controllers.asset.delete_asset(db, asset)
    
    return DeleteAssetResponse(
        deleted_asset_id=asset_id,
        deleted_file=file_deleted
    )
