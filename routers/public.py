"""
Public view router.

Unauthenticated endpoints for viewing publicly shared content:
- GET /public/view/{magic_id} - View a public folder, asset, or artifact
- GET /public/assets/{magic_id}/download - Download/stream a public asset (supports range requests)
- GET /public/repo/{magic_id} - Public repo metadata
- GET /public/repo/{magic_id}/tree - Public repo file tree
- GET /public/repo/{magic_id}/files/{path} - Public repo file contents
- GET /public/repo/{magic_id}/commits - Public repo commit history
"""
import os
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
    request: Request,
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
        # Include publish config for repos
        publish_config = None
        if item.type == "repo":
            meta = item.meta or {}
            pub = meta.get("publish", {})
            if pub.get("enabled"):
                publish_config = {
                    "render_mode": pub.get("render_mode", "embedded"),
                    "slug": pub.get("slug", ""),
                    "allow_public_code_view": pub.get("allow_public_code_view", False),
                }
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
                "publish": publish_config,
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


# ============================================================================
# Public Repository Endpoints
# ============================================================================

import subprocess
from typing import Optional, List, Dict, Any
from uuid import UUID

REPOS_DIR = os.path.join(os.environ.get("STORAGE_PATH", "/app/storage"), "repos")


def _get_repo_path(artifact_id: UUID) -> str:
    return os.path.join(REPOS_DIR, f"{artifact_id}.git")


def _repo_exists(artifact_id: UUID) -> bool:
    return os.path.exists(_get_repo_path(artifact_id))


def _run_git_command(artifact_id: UUID, *args: str) -> subprocess.CompletedProcess:
    repo_path = _get_repo_path(artifact_id)
    cmd = ["git", "--git-dir", repo_path] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _get_repo_size(artifact_id: UUID) -> int:
    repo_path = _get_repo_path(artifact_id)
    total = 0
    if os.path.exists(repo_path):
        for dirpath, _dirnames, filenames in os.walk(repo_path):
            for f in filenames:
                total += os.path.getsize(os.path.join(dirpath, f))
    return total


def _resolve_public_repo(db: Session, magic_id: UUID):
    """Resolve a magic_id to a public repo artifact. Returns (artifact, error_response)."""
    item, kind = controllers.public.resolve_public_item(db, magic_id)
    if not item or kind != "artifact" or item.type != "repo":
        return None, HTTPException(status_code=404, detail="Public repository not found")
    return item, None


@router.get("/repo/{magic_id}")
async def public_repo_metadata(magic_id: UUID, request: Request, db: Session = Depends(get_db)):
    """Get public repository metadata."""
    artifact, err = _resolve_public_repo(db, magic_id)
    if err:
        raise err

    artifact_id = UUID(str(artifact.id))

    # Build clone URL from request base URL
    base_url = os.environ.get("PUBLIC_URL") or str(request.base_url).rstrip("/")
    clone_url = f"{base_url}/git/{artifact_id}.git"

    if not _repo_exists(artifact_id):
        return {"name": artifact.name, "description": artifact.description, "commit_count": 0, "file_count": 0, "repo_size_bytes": 0, "last_commit": None, "clone_url": clone_url, "publish": None}

    last_commit = None
    result = _run_git_command(artifact_id, "log", "-1", "--format=%H|%s|%an <%ae>|%aI")
    if result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split("|", 3)
        if len(parts) >= 4:
            last_commit = {"hash": parts[0][:7], "message": parts[1], "author": parts[2], "date": parts[3]}

    commit_count = 0
    result = _run_git_command(artifact_id, "rev-list", "--count", "HEAD")
    if result.returncode == 0:
        try:
            commit_count = int(result.stdout.strip())
        except ValueError:
            pass

    file_count = 0
    result = _run_git_command(artifact_id, "ls-tree", "-r", "HEAD", "--name-only")
    if result.returncode == 0:
        file_count = len([l for l in result.stdout.strip().split("\n") if l])

    # Include publish config for static site detection
    pub = (artifact.meta or {}).get("publish", {})
    publish = None
    if pub.get("enabled"):
        site_url = None
        slug = pub.get("slug", "")
        if slug:
            public_url = os.environ.get("PUBLIC_URL") or str(request.base_url).rstrip("/")
            site_url = f"{public_url}/published/{slug}/"
        publish = {
            "enabled": True,
            "slug": slug,
            "render_mode": pub.get("render_mode", "embedded"),
            "allow_public_code_view": pub.get("allow_public_code_view", False),
            "site_url": site_url,
        }

    return {
        "name": artifact.name,
        "description": artifact.description,
        "commit_count": commit_count,
        "file_count": file_count,
        "repo_size_bytes": _get_repo_size(artifact_id),
        "last_commit": last_commit,
        "clone_url": clone_url,
        "publish": publish,
    }


@router.get("/repo/{magic_id}/tree")
async def public_repo_tree(magic_id: UUID, ref: str = "HEAD", path: str = "", db: Session = Depends(get_db)):
    """Get file tree for a public repository."""
    artifact, err = _resolve_public_repo(db, magic_id)
    if err:
        raise err

    artifact_id = UUID(str(artifact.id))
    if not _repo_exists(artifact_id):
        raise HTTPException(status_code=404, detail="Repository not initialized")

    tree_path = f"{ref}:{path}" if path else ref
    result = _run_git_command(artifact_id, "ls-tree", "-l", tree_path)
    if result.returncode != 0:
        raise HTTPException(status_code=404, detail=f"Path not found: {path} at ref {ref}")

    items = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        meta, name = parts
        meta_parts = meta.split()
        if len(meta_parts) < 4:
            continue
        item_type = meta_parts[1]
        size_str = meta_parts[3] if len(meta_parts) > 3 else None
        item_path = f"{path}/{name}" if path else name
        items.append({"name": name, "path": item_path, "type": item_type, "size": int(size_str) if size_str and item_type == "blob" else None})

    return {"ref": ref, "items": items}


@router.get("/repo/{magic_id}/files/{file_path:path}")
async def public_repo_file(magic_id: UUID, file_path: str, ref: str = "HEAD", db: Session = Depends(get_db)):
    """Get raw file contents from a public repository."""
    artifact, err = _resolve_public_repo(db, magic_id)
    if err:
        raise err

    artifact_id = UUID(str(artifact.id))
    if not _repo_exists(artifact_id):
        raise HTTPException(status_code=404, detail="Repository not initialized")

    result = _run_git_command(artifact_id, "cat-file", "-t", f"{ref}:{file_path}")
    if result.returncode != 0:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    obj_type = result.stdout.strip()
    if obj_type != "blob":
        raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")

    result = _run_git_command(artifact_id, "cat-file", "-s", f"{ref}:{file_path}")
    file_size = 0
    if result.returncode == 0:
        try:
            file_size = int(result.stdout.strip())
        except ValueError:
            pass

    result = _run_git_command(artifact_id, "show", f"{ref}:{file_path}")
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="Failed to read file contents")

    content = result.stdout
    is_binary = '\x00' in content
    if is_binary:
        content = "[Binary file - cannot display]"

    return {"path": file_path, "ref": ref, "content": content, "size": file_size, "is_binary": is_binary}


@router.get("/repo/{magic_id}/commits")
async def public_repo_commits(magic_id: UUID, ref: str = "HEAD", limit: int = 50, db: Session = Depends(get_db)):
    """Get commit history for a public repository."""
    artifact, err = _resolve_public_repo(db, magic_id)
    if err:
        raise err

    artifact_id = UUID(str(artifact.id))
    if not _repo_exists(artifact_id):
        raise HTTPException(status_code=404, detail="Repository not initialized")

    limit = min(limit, 200)
    result = _run_git_command(artifact_id, "log", ref, f"--max-count={limit}", "--format=%H|%s|%an <%ae>|%aI")

    commits = []
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append({"hash": parts[0][:7], "message": parts[1], "author": parts[2], "date": parts[3]})

    return {"commits": commits}


@router.get("/repo/{magic_id}/commits/{commit_hash}")
async def public_repo_commit_detail(magic_id: UUID, commit_hash: str, db: Session = Depends(get_db)):
    """Get detailed info for a single commit, including file diffs."""
    artifact, err = _resolve_public_repo(db, magic_id)
    if err:
        raise err

    artifact_id = UUID(str(artifact.id))
    if not _repo_exists(artifact_id):
        raise HTTPException(status_code=404, detail="Repository not initialized")

    result = _run_git_command(artifact_id, "cat-file", "-t", commit_hash)
    if result.returncode != 0:
        raise HTTPException(status_code=404, detail=f"Commit not found: {commit_hash}")

    result = _run_git_command(artifact_id, "log", "-1", "--format=%H|%s|%an <%ae>|%aI|%P", commit_hash)
    if result.returncode != 0 or not result.stdout.strip():
        raise HTTPException(status_code=500, detail="Failed to read commit")

    parts = result.stdout.strip().split("|", 4)
    full_hash = parts[0]
    message = parts[1] if len(parts) > 1 else ""
    author = parts[2] if len(parts) > 2 else ""
    date = parts[3] if len(parts) > 3 else ""
    parent_hash = parts[4][:7] if len(parts) > 4 and parts[4] else None

    result = _run_git_command(artifact_id, "diff", "--stat-width=200", "--patch", f"{commit_hash}~1", commit_hash)
    if result.returncode != 0:
        result = _run_git_command(artifact_id, "diff", "--stat-width=200", "--patch", "--root", commit_hash)

    files = []
    total_additions = 0
    total_deletions = 0

    if result.returncode == 0 and result.stdout.strip():
        raw_diff = result.stdout
        current_file = None
        current_status = "modified"
        current_lines = []
        current_additions = 0
        current_deletions = 0

        def _save_file():
            if current_file:
                files.append({"path": current_file, "status": current_status, "additions": current_additions, "deletions": current_deletions, "patch": "\n".join(current_lines)})

        for line in raw_diff.split("\n"):
            if line.startswith("diff --git"):
                _save_file()
                path_parts = line.split(" b/", 1)
                current_file = path_parts[1] if len(path_parts) > 1 else "unknown"
                current_status = "modified"
                current_lines = [line]
                current_additions = 0
                current_deletions = 0
            elif line.startswith("new file"):
                current_status = "added"
                current_lines.append(line)
            elif line.startswith("deleted file"):
                current_status = "deleted"
                current_lines.append(line)
            elif line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@"):
                current_lines.append(line)
            elif line.startswith("+") and not line.startswith("+++"):
                current_additions += 1
                total_additions += 1
                current_lines.append(line)
            elif line.startswith("-") and not line.startswith("---"):
                current_deletions += 1
                total_deletions += 1
                current_lines.append(line)
            else:
                current_lines.append(line)

        _save_file()

    return {
        "hash": full_hash,
        "short_hash": full_hash[:7],
        "message": message,
        "author": author,
        "date": date,
        "parent_hash": parent_hash,
        "files": files,
        "total_additions": total_additions,
        "total_deletions": total_deletions,
    }
