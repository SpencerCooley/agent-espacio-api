"""
Folders router.

Endpoints for folder management (hierarchical file storage):
- GET /folders - List all folders (tree view)
- POST /folders - Create new folder
- GET /folders/{folder_id} - Get folder details
- GET /folders/{folder_id}/contents - Get folder contents (subfolders + assets)
- PUT /folders/{folder_id} - Update folder (rename/move)
- DELETE /folders/{folder_id} - Delete folder and all contents
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from dependencies.dependencies import get_db, require_user
from models.user import User
from types_definitions.folder import (
    CreateFolderRequest,
    UpdateFolderRequest,
    FolderResponse,
    FolderListResponse,
    FolderContentsResponse,
    DeleteFolderResponse,
)
from types_definitions.asset import AssetResponse
import controllers

router = APIRouter(
    prefix="/folders",
    tags=["Folders"],
    responses={404: {"description": "Not found"}}
)


@router.get("", response_model=FolderListResponse)
async def list_folders(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    List all folders as a tree structure.
    
    Returns folders organized hierarchically starting from "My Drive".
    """
    # Get root folder first
    root = controllers.folder.get_root_folder(db)
    
    folders = []
    if root:
        # Build tree starting from root
        all_folders = controllers.folder.get_folder_tree(db)
        
        # Create a mapping for tree building
        folder_map = {f.id: f for f in all_folders}
        folder_map[root.id] = root
        
        # Build tree recursively
        def build_tree(parent_id, depth=0):
            result = []
            children = [f for f in all_folders if f.parent_id == parent_id]
            for child in children:
                tree_item = {
                    "id": child.id,
                    "name": child.name,
                    "parent_id": child.parent_id,
                    "path": child.path,
                    "is_root": child.is_root,
                    "created_at": child.created_at,
                    "children": build_tree(child.id, depth + 1)
                }
                result.append(tree_item)
            return result
        
        # Start building from root's children
        folders = build_tree(root.id)
    
    # Count total folders
    total = len(folders)
    
    return FolderListResponse(folders=folders, total=total)


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    request: CreateFolderRequest,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Create a new folder.
    
    - **name**: Folder name
    - **parent_id**: Parent folder ID (null for root level under "My Drive")
    """
    folder = controllers.folder.create_folder(
        db=db,
        name=request.name,
        created_by=current_user,
        parent_id=request.parent_id
    )
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent folder not found"
        )
    
    return folder


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: UUID,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Get folder details by ID.
    """
    folder = controllers.folder.get_folder(db, folder_id)
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    return folder


@router.get("/{folder_id}/contents", response_model=FolderContentsResponse)
async def get_folder_contents(
    folder_id: UUID,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Get folder contents including subfolders and assets.
    
    Returns both immediate subfolders and assets in the folder.
    """
    folder = controllers.folder.get_folder(db, folder_id)
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    subfolders, assets = controllers.folder.get_folder_contents(db, folder_id)
    
    # Convert assets to response format
    asset_responses = [AssetResponse.from_orm(a) for a in assets]
    
    return FolderContentsResponse(
        folder=folder,
        subfolders=subfolders,
        assets=asset_responses,
        total_subfolders=len(subfolders),
        total_assets=len(assets)
    )


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: UUID,
    request: UpdateFolderRequest,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Update a folder (rename or move).
    
    - **name**: New folder name
    - **parent_id**: New parent folder ID (for moving)
    """
    folder = controllers.folder.get_folder(db, folder_id)
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    try:
        updated = controllers.folder.update_folder(
            db=db,
            folder=folder,
            name=request.name,
            parent_id=request.parent_id
        )
        return updated
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{folder_id}", response_model=DeleteFolderResponse)
async def delete_folder(
    folder_id: UUID,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Delete a folder and ALL its contents recursively.
    
    ⚠️ **Warning**: This will permanently delete:
    - The folder itself
    - All subfolders
    - All assets in the folder and subfolders
    - All files from disk storage
    
    This action cannot be undone.
    """
    folder = controllers.folder.get_folder(db, folder_id)
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    try:
        subfolders_count, assets_count = controllers.folder.delete_folder(db, folder)
        
        return DeleteFolderResponse(
            deleted_folder_id=folder_id,
            deleted_subfolders_count=subfolders_count,
            deleted_assets_count=assets_count
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
