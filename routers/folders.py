"""
Folders router.

Endpoints for folder management (hierarchical file storage):
- GET /folders - List folders (full tree for admin; grant forest for editors)
- GET /folders/scoped/search - Search across principal's scope forest
- POST /folders - Create new folder
- GET /folders/{folder_id} - Get folder details
- GET /folders/{folder_id}/contents - Get folder contents (subfolders + assets)
- PUT /folders/{folder_id} - Update folder (rename/move)
- DELETE /folders/{folder_id} - Delete folder and all contents
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID

from dependencies.dependencies import get_db, require_auth, get_scope
from models.user import User
from services.permissions import (
    Scope,
    assert_folder_in_scope,
    assert_folder_id_in_scope,
    folder_in_scope,
    get_scope_folder_ids,
)
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


def _folder_item_response(f) -> FolderItemResponse:
    return FolderItemResponse(
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
    )


def _asset_item_response(a) -> FolderItemResponse:
    return FolderItemResponse(
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
    )


def _artifact_item_response(ar) -> FolderItemResponse:
    return FolderItemResponse(
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
    )


def _build_tree_from_folders(all_folders, root_parent_ids):
    """Build nested tree items from a flat folder list, rooted at given parent ids."""
    def build_tree(parent_id):
        result = []
        children = [f for f in all_folders if f.parent_id == parent_id]
        for child in children:
            result.append({
                "id": child.id,
                "name": child.name,
                "parent_id": child.parent_id,
                "path": child.path,
                "is_root": child.is_root,
                "created_at": child.created_at,
                "children": build_tree(child.id),
            })
        return result

    folders = []
    for pid in root_parent_ids:
        folders.extend(build_tree(pid))
    return folders


@router.get("", response_model=FolderListResponse)
async def list_folders(
    current_user: Optional[User] = Depends(require_auth),
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db)
):
    """
    List folders as a tree structure.

    Admin / global keys: full tree under My Drive.
    Editors: forest of granted folders (and their descendants).
    Zero grants: empty list.
    """
    root = controllers.folder.get_root_folder(db)
    folders = []

    if scope.is_unrestricted:
        if root:
            all_folders = controllers.folder.get_folder_tree(db)
            folders = _build_tree_from_folders(all_folders, [root.id])
    else:
        grant_ids = scope.grant_folder_ids or set()
        if grant_ids:
            all_folders = controllers.folder.get_folder_tree(db)
            scoped = [f for f in all_folders if folder_in_scope(db, scope, f)]
            scoped_ids = {f.id for f in scoped}
            # Top-level = folders whose parent is outside the scoped set
            # (grant roots, or children of root / out-of-scope parents)
            top_level = [
                f for f in scoped
                if f.parent_id is None or f.parent_id not in scoped_ids
            ]
            # Emit each top-level grant as a tree root (parent_id kept as-is)
            def build_from(folder):
                return {
                    "id": folder.id,
                    "name": folder.name,
                    "parent_id": folder.parent_id,
                    "path": folder.path,
                    "is_root": folder.is_root,
                    "created_at": folder.created_at,
                    "children": [
                        build_from(c)
                        for c in scoped
                        if c.parent_id == folder.id
                    ],
                }
            folders = [build_from(f) for f in top_level]

    return FolderListResponse(folders=folders, total=len(folders))


@router.get("/scoped/search", response_model=FolderContentsResponse)
async def search_scoped_items(
    q: str = Query(..., min_length=1),
    current_user: Optional[User] = Depends(require_auth),
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db),
):
    """
    Search for items by name across the principal's entire scope forest.

    Editors search only within granted subtrees. Admins search the full tree.
    """
    root = controllers.folder.get_root_folder(db)
    if not root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Root folder not found",
        )

    folder_ids = get_scope_folder_ids(db, scope)
    folders_result, assets_result, artifacts_result = (
        controllers.folder.search_within_folder_ids(db, folder_ids, q.strip())
    )

    items = (
        [_folder_item_response(f) for f in folders_result]
        + [_asset_item_response(a) for a in assets_result]
        + [_artifact_item_response(ar) for ar in artifacts_result]
    )
    items.sort(key=lambda x: x.name.lower())

    return FolderContentsResponse(
        folder=root,
        items=items,
        total_items=len(items),
    )


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    request: CreateFolderRequest,
    current_user: Optional[User] = Depends(require_auth),
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db)
):
    """
    Create a new folder.

    - **name**: Folder name
    - **parent_id**: Parent folder ID (null for root level under "My Drive")

    Editors must create inside an in-scope parent (cannot create at root).
    """
    parent_id = request.parent_id
    if parent_id is None:
        root = controllers.folder.get_root_folder(db)
        if not root:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Root folder not found",
            )
        parent_id = root.id

    assert_folder_id_in_scope(db, scope, parent_id, detail="Parent folder is out of scope")

    folder = controllers.folder.create_folder(
        db=db,
        name=request.name,
        created_by=current_user,
        parent_id=parent_id,
    )
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent folder not found"
        )
    
    actor = {
        "type": "agent" if current_user is None else "user",
        "id": str(current_user.id) if current_user else None,
        "name": current_user.email if current_user else None,
    }
    parent_id_str = str(folder.parent_id) if folder.parent_id else "00000000-0000-0000-0000-000000000001"
    publish_event(
        event_type="folder.created",
        folder_id=parent_id_str,
        resource_id=str(folder.id),
        payload={"name": folder.name},
        actor=actor,
    )
    publish_event(
        event_type="folder_contents_changed",
        folder_id=parent_id_str,
        resource_id=str(folder.id),
        payload={"name": folder.name},
        actor=actor,
    )
    
    return folder


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db)
):
    """Get folder details by ID."""
    folder = controllers.folder.get_folder(db, folder_id)
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    assert_folder_in_scope(db, scope, folder)
    return folder


@router.get("/{folder_id}/ancestors", response_model=FolderAncestorsResponse)
async def get_folder_ancestors(
    folder_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db)
):
    """
    Get the ancestor chain for a folder, from root down to the folder itself.

    For scoped principals, the chain is clamped at grant root(s) — ancestors
    outside the principal's grants are omitted.
    """
    folder = controllers.folder.get_folder(db, folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    assert_folder_in_scope(db, scope, folder)

    ancestors = controllers.folder.get_folder_ancestors(db, folder_id)
    if not scope.is_unrestricted:
        ancestors = [a for a in ancestors if folder_in_scope(db, scope, a)]

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
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db)
):
    """
    Get folder contents including subfolders, assets, and artifacts.

    Returns a unified list of all items in the folder, ordered alphabetically by name.
    """
    folder = controllers.folder.get_folder(db, folder_id)

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    assert_folder_in_scope(db, scope, folder)

    subfolders, assets, artifacts = controllers.folder.get_folder_contents(db, folder_id)

    items = (
        [_folder_item_response(f) for f in subfolders]
        + [_asset_item_response(a) for a in assets]
        + [_artifact_item_response(ar) for ar in artifacts]
    )
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
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db)
):
    """
    Search for items by name within a folder and all its subfolders.
    """
    folder = controllers.folder.get_folder(db, folder_id)

    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    assert_folder_in_scope(db, scope, folder)

    if not q or not q.strip():
        return FolderContentsResponse(
            folder=folder,
            items=[],
            total_items=0
        )

    folders_result, assets_result, artifacts_result = controllers.folder.search_folder_scope(
        db, folder_id, q.strip()
    )

    items = (
        [_folder_item_response(f) for f in folders_result]
        + [_asset_item_response(a) for a in assets_result]
        + [_artifact_item_response(ar) for ar in artifacts_result]
    )
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
    scope: Scope = Depends(get_scope),
    db: Session = Depends(get_db)
):
    """
    Update a folder (rename or move).
    
    - **name**: New folder name
    - **parent_id**: New parent folder ID (for moving)

    Move requires both source and destination in scope.
    """
    folder = controllers.folder.get_folder(db, folder_id)
    
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found"
        )

    assert_folder_in_scope(db, scope, folder)

    if request.parent_id is not None:
        assert_folder_id_in_scope(
            db, scope, request.parent_id, detail="Destination folder is out of scope"
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
    scope: Scope = Depends(get_scope),
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

    assert_folder_in_scope(db, scope, folder)
    
    try:
        parent_id = str(folder.parent_id) if folder.parent_id else "00000000-0000-0000-0000-000000000001"
        subfolders_count, assets_count = controllers.folder.delete_folder(db, folder)
        
        actor = {
            "type": "user" if current_user else "agent",
            "id": str(current_user.id) if current_user else None,
            "name": current_user.email if current_user else None,
        }
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
    scope: Scope = Depends(get_scope),
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

    assert_folder_in_scope(db, scope, folder)
    
    if folder.is_root:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Root folder cannot be shared publicly"
        )
    
    updated = controllers.folder.share.toggle_folder_share(db, folder)
    return updated
