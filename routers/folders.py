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
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from dependencies.dependencies import get_db, require_auth
from models.user import User
from types_definitions.folder import (
    CreateFolderRequest,
    UpdateFolderRequest,
    FolderResponse,
    FolderListResponse,
    FolderContentsResponse,
    FolderAncestorsResponse,
    DeleteFolderResponse,
)
from types_definitions.artifact import FolderItemResponse
import controllers
from services.events import publish_event

router = APIRouter(
    prefix="/folders",
    tags=["Folders"],
    responses={404: {"description": "Not found"}}
)


@router.get("", response_model=FolderListResponse)
async def list_folders(
    current_user: Optional[User] = Depends(require_auth),
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
    current_user: Optional[User] = Depends(require_auth),
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
    
    # Broadcast creation events for all actors (human + agent)
    actor = {"type": "agent" if current_user is None else "user", "id": str(current_user.id) if current_user else None, "name": current_user.email if current_user else None}
    parent_id = str(folder.parent_id) if folder.parent_id else "00000000-0000-0000-0000-000000000001"
    publish_event(
        event_type="folder.created",
        folder_id=parent_id,
        resource_id=str(folder.id),
        payload={"name": folder.name},
        actor=actor,
    )
    publish_event(
        event_type="folder_contents_changed",
        folder_id=parent_id,
        resource_id=str(folder.id),
        payload={"name": folder.name},
        actor=actor,
    )
    
    return folder


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
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


@router.get("/{folder_id}/ancestors", response_model=FolderAncestorsResponse)
async def get_folder_ancestors(
    folder_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get the ancestor chain for a folder, from root down to the folder itself.
    
    Useful for building breadcrumb navigation.
    """
    ancestors = controllers.folder.get_folder_ancestors(db, folder_id)
    
    if not ancestors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    return FolderAncestorsResponse(ancestors=ancestors)


@router.get("/{folder_id}/contents", response_model=FolderContentsResponse)
async def get_folder_contents(
    folder_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get folder contents including subfolders, assets, and artifacts.

    Returns a unified list of all items in the folder, ordered alphabetically by name.
    The 'kind' field indicates whether each item is a folder, asset, or artifact.
    """
    folder = controllers.folder.get_folder(db, folder_id)

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    subfolders, assets, artifacts = controllers.folder.get_folder_contents(db, folder_id)

    # Build unified items list
    items = []

    for f in subfolders:
        items.append(FolderItemResponse(
            kind="folder",
            id=f.id,
            name=f.name,
            type=None,
            mime_type=None,
            size_bytes=None,
            is_image=None,
            is_public=f.is_public,
            public_magic_id=f.public_magic_id,
            created_at=f.created_at,
            updated_at=f.updated_at,
        ))

    for a in assets:
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
            public_magic_id=a.public_magic_id,
            created_at=a.created_at,
            updated_at=a.updated_at,
        ))

    for ar in artifacts:
        items.append(FolderItemResponse(
            kind="artifact",
            id=ar.id,
            name=ar.name,
            type=ar.type,
            mime_type=None,
            size_bytes=None,
            is_image=None,
            is_public=ar.is_public,
            public_magic_id=ar.public_magic_id,
            created_at=ar.created_at,
            updated_at=ar.updated_at,
        ))

    # Sort alphabetically by name across all types
    items.sort(key=lambda x: x.name.lower())

    return FolderContentsResponse(
        folder=folder,
        items=items,
        total_items=len(items)
    )


@router.get("/{folder_id}/search", response_model=FolderContentsResponse)
async def search_folder_items(
    folder_id: UUID,
    q: str,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Search for items by name within a folder and all its subfolders.

    Searches folder names, asset names, and artifact names using
    case-insensitive partial matching.

    Query param:
        q: Search term

    Returns a unified list of matching items in the same shape as folder contents.
    """
    folder = controllers.folder.get_folder(db, folder_id)

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    if not q or not q.strip():
        return FolderContentsResponse(
            folder=folder,
            items=[],
            total_items=0
        )

    folders_result, assets_result, artifacts_result = controllers.folder.search_folder_scope(
        db, folder_id, q.strip()
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
            public_magic_id=ar.public_magic_id,
            created_at=ar.created_at,
            updated_at=ar.updated_at,
        ))

    # Sort alphabetically by name across all types
    items.sort(key=lambda x: x.name.lower())

    return FolderContentsResponse(
        folder=folder,
        items=items,
        total_items=len(items)
    )


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: UUID,
    request: UpdateFolderRequest,
    current_user: Optional[User] = Depends(require_auth),
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
    current_user: Optional[User] = Depends(require_auth),
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
        parent_id = str(folder.parent_id) if folder.parent_id else "00000000-0000-0000-0000-000000000001"
        subfolders_count, assets_count = controllers.folder.delete_folder(db, folder)
        
        actor = {"type": "user", "id": str(current_user.id) if current_user else None, "name": current_user.email if current_user else None}
        publish_event(
            event_type="folder.deleted",
            folder_id=parent_id,
            resource_id=str(folder_id),
            payload={"name": folder.name},
            actor=actor,
        )
        publish_event(
            event_type="folder_contents_changed",
            folder_id=parent_id,
            resource_id=str(folder_id),
            payload={"name": folder.name},
            actor=actor,
        )
        
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


@router.post("/{folder_id}/share", response_model=FolderResponse)
async def share_folder(
    folder_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Toggle public sharing for a folder.
    
    Generates a public_magic_id when making public, clears it when making private.
    Root folder cannot be shared.
    """
    folder = controllers.folder.get_folder(db, folder_id)
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )
    
    if folder.is_root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Root folder cannot be shared publicly"
        )
    
    updated = controllers.folder.share.toggle_folder_share(db, folder)
    return updated
