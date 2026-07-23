"""
Repository router.

Endpoints for browsing git repository artifacts:
- GET /artifacts/{id}/repo - Repo metadata
- GET /artifacts/{id}/repo/tree - File tree
- GET /artifacts/{id}/repo/files/{path} - Raw file contents
- GET /artifacts/{id}/repo/commits - Commit history
- GET/PUT/DELETE /artifacts/{id}/publish - Publishing settings
- POST /artifacts/{id}/deploy - Manual deploy
- GET /artifacts/{id}/deploy/status - Deploy status
"""
import os
import re
import shutil
import subprocess
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, Field

from dependencies.dependencies import get_db, require_auth
from models.user import User
from models.artifact import Artifact
import controllers

router = APIRouter(
    prefix="/artifacts",
    tags=["Repositories"],
    responses={404: {"description": "Not found"}}
)

STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
REPOS_DIR = os.path.join(STORAGE_PATH, "repos")
PUBLISHED_DIR = os.path.join(STORAGE_PATH, "published")


# ============================================================================
# Pydantic Response Models
# ============================================================================


class PublishConfig(BaseModel):
    """Publishing configuration stored in artifact meta."""
    enabled: bool = Field(default=False, description="Whether publishing is enabled")
    slug: str = Field(default="", description="URL slug for the published site")
    render_mode: str = Field(default="embedded", description="How the public view renders: 'embedded', 'direct', or 'repo_link'")
    build_command: str = Field(default="", description="Build command (e.g. 'npm run build'). Empty = serve as-is")
    output_dir: str = Field(default="dist", description="Build output directory relative to repo root")
    auto_deploy: bool = Field(default=True, description="Automatically deploy on push")
    allow_public_code_view: bool = Field(default=False, description="Allow public access to repo code via ?repo_view=true")
    status: str = Field(default="idle", description="Current deploy status: 'idle', 'building', 'deployed', 'failed'")
    last_deploy_at: Optional[str] = Field(None, description="ISO timestamp of last deploy")
    last_deploy_commit: Optional[str] = Field(None, description="Short SHA of last deployed commit")
    last_deploy_log: Optional[str] = Field(None, description="Truncated build log from last deploy")


class RepoMetadataResponse(BaseModel):
    name: str = Field(..., description="Repository name")
    description: Optional[str] = Field(None, description="Repository description")
    artifact_id: str = Field(..., description="Artifact UUID")
    git_remote_url: str = Field(..., description="Git SSH remote URL")
    clone_url: str = Field(default="", description="Git HTTP clone URL for public repos")
    default_branch: str = Field(default="master", description="Default branch name")
    last_commit: Optional[Dict[str, Any]] = Field(None, description="Last commit info")
    commit_count: int = Field(default=0, description="Total commits")
    file_count: int = Field(default=0, description="Files at HEAD")
    repo_size_bytes: int = Field(default=0, description="Size of bare repo on disk")
    publish: Optional[PublishConfig] = Field(None, description="Publish settings (if configured)")


class RepoTreeItem(BaseModel):
    name: str = Field(..., description="File or directory name")
    path: str = Field(..., description="Full path within repo")
    type: str = Field(..., description="'blob' for file, 'tree' for directory")
    size: Optional[int] = Field(None, description="File size in bytes (files only)")


class RepoTreeResponse(BaseModel):
    ref: str = Field(..., description="Git ref (branch, tag, or commit)")
    items: List[RepoTreeItem] = Field(default_factory=list, description="Tree entries")


class RepoCommit(BaseModel):
    hash: str = Field(..., description="Commit SHA")
    message: str = Field(..., description="Commit message")
    author: str = Field(..., description="Author name and email")
    date: str = Field(..., description="Commit date ISO string")


class RepoCommitsResponse(BaseModel):
    commits: List[RepoCommit] = Field(default_factory=list, description="Commit history")


class RepoDiffFile(BaseModel):
    path: str = Field(..., description="File path")
    status: str = Field(..., description="'added', 'deleted', 'modified', or 'renamed'")
    additions: int = Field(default=0, description="Lines added")
    deletions: int = Field(default=0, description="Lines deleted")
    patch: Optional[str] = Field(None, description="Unified diff patch")


class RepoCommitDetailResponse(BaseModel):
    hash: str = Field(..., description="Full commit SHA")
    short_hash: str = Field(..., description="7-char short SHA")
    message: str = Field(..., description="Commit message")
    author: str = Field(..., description="Author name and email")
    date: str = Field(..., description="Commit date ISO string")
    parent_hash: Optional[str] = Field(None, description="Parent commit short SHA")
    files: List[RepoDiffFile] = Field(default_factory=list, description="Changed files")
    total_additions: int = Field(default=0, description="Total lines added")
    total_deletions: int = Field(default=0, description="Total lines deleted")


class RepoFileResponse(BaseModel):
    path: str = Field(..., description="File path")
    ref: str = Field(..., description="Git ref")
    content: str = Field(..., description="Raw file contents as text")
    size: int = Field(..., description="File size in bytes")
    is_binary: bool = Field(default=False, description="Whether file is binary")


# ============================================================================
# Publish / Deploy Models
# ============================================================================


class PublishSettingsRequest(BaseModel):
    """Request to update publish settings."""
    enabled: Optional[bool] = Field(None)
    slug: Optional[str] = Field(None)
    render_mode: Optional[str] = Field(None)
    build_command: Optional[str] = Field(None)
    output_dir: Optional[str] = Field(None)
    auto_deploy: Optional[bool] = Field(None)
    allow_public_code_view: Optional[bool] = Field(None)


class PublishSettingsResponse(BaseModel):
    """Response with current publish settings."""
    enabled: bool
    slug: str
    render_mode: str
    build_command: str
    output_dir: str
    auto_deploy: bool
    allow_public_code_view: bool
    status: str
    last_deploy_at: Optional[str]
    last_deploy_commit: Optional[str]
    site_url: str = Field(default="", description="Full URL to the published site")


class DeployStatusResponse(BaseModel):
    """Response for deploy status."""
    status: str
    last_deploy_at: Optional[str]
    last_deploy_commit: Optional[str]
    last_deploy_log: Optional[str]


# ============================================================================
# Helper Functions
# ============================================================================

def _get_repo_path(artifact_id: UUID) -> str:
    """Get the filesystem path for a bare repo."""
    return os.path.join(REPOS_DIR, f"{artifact_id}.git")


def _repo_exists(artifact_id: UUID) -> bool:
    """Check if a bare repo exists on disk."""
    return os.path.exists(_get_repo_path(artifact_id))


def _run_git_command(artifact_id: UUID, *args: str) -> subprocess.CompletedProcess:
    """Run a git command against a bare repo."""
    repo_path = _get_repo_path(artifact_id)
    cmd = ["git", "--git-dir", repo_path] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    return result


def _get_repo_size(artifact_id: UUID) -> int:
    """Get total size of bare repo directory in bytes."""
    repo_path = _get_repo_path(artifact_id)
    total = 0
    if os.path.exists(repo_path):
        for dirpath, _dirnames, filenames in os.walk(repo_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total += os.path.getsize(fp)
    return total


def _get_publish_config(artifact: Artifact) -> PublishConfig:
    """Extract publish config from artifact meta."""
    meta = artifact.meta or {}
    pub = meta.get("publish", {})
    return PublishConfig(
        enabled=pub.get("enabled", False),
        slug=pub.get("slug", ""),
        render_mode=pub.get("render_mode", "embedded"),
        build_command=pub.get("build_command", ""),
        output_dir=pub.get("output_dir", "dist"),
        auto_deploy=pub.get("auto_deploy", True),
        allow_public_code_view=pub.get("allow_public_code_view", False),
        status=pub.get("status", "idle"),
        last_deploy_at=pub.get("last_deploy_at"),
        last_deploy_commit=pub.get("last_deploy_commit"),
        last_deploy_log=pub.get("last_deploy_log"),
    )


def _save_publish_config(artifact: Artifact, db: Session, updates: dict) -> None:
    """Merge publish config updates into artifact meta and persist."""
    meta = artifact.meta or {}
    pub = meta.get("publish", {})
    pub.update({k: v for k, v in updates.items() if v is not None})
    meta["publish"] = pub
    artifact.meta = meta
    flag_modified(artifact, "meta")
    db.commit()


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug[:64] or 'site'


def _get_site_url(request: Request, slug: str) -> str:
    """Build the full URL for a published site."""
    public_url = os.environ.get("PUBLIC_URL", "")
    if not public_url:
        public_url = str(request.base_url).rstrip("/")
    return f"{public_url}/published/{slug}/"


def _get_published_path(artifact_id: UUID) -> str:
    """Get the filesystem path for published site files."""
    return os.path.join(PUBLISHED_DIR, str(artifact_id))


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/{artifact_id}/repo", response_model=RepoMetadataResponse)
async def get_repo_metadata(
    artifact_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get repository metadata for a repo artifact.
    
    Returns git remote URL, last commit info, file count, and repo size.
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    if artifact.type != "repo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact is not a repository"
        )
    
    # Build git remote URL (use API_HOST env or default)
    api_host = os.environ.get("API_HOST", "localhost")
    # If API_HOST is 0.0.0.0, use a more useful default
    if api_host in ("0.0.0.0", "127.0.0.1"):
        api_host = "localhost"
    git_remote_url = f"ssh://git@{api_host}:2222/repos/{artifact_id}.git"

    # Build HTTP clone URL for public repos
    public_url = os.environ.get("PUBLIC_URL", "")
    if not public_url:
        public_url = f"https://{api_host}" if api_host != "localhost" else "http://localhost:8000"
    clone_url = f"{public_url}/git/{artifact_id}.git"
    
    # Check if repo exists on disk
    if not _repo_exists(artifact_id):
        return RepoMetadataResponse(
            name=artifact.name,
            description=artifact.description,
            artifact_id=str(artifact_id),
            git_remote_url=git_remote_url,
            clone_url=clone_url,
            default_branch="master",
            last_commit=None,
            commit_count=0,
            file_count=0,
            repo_size_bytes=0,
            publish=_get_publish_config(artifact),
        )
    
    # Get last commit
    last_commit = None
    result = _run_git_command(artifact_id, "log", "-1", "--format=%H|%s|%an <%ae>|%aI")
    if result.returncode == 0 and result.stdout.strip():
        parts = result.stdout.strip().split("|", 3)
        if len(parts) >= 4:
            last_commit = {
                "hash": parts[0][:7],
                "message": parts[1],
                "author": parts[2],
                "date": parts[3],
            }
    
    # Get commit count
    commit_count = 0
    result = _run_git_command(artifact_id, "rev-list", "--count", "HEAD")
    if result.returncode == 0:
        try:
            commit_count = int(result.stdout.strip())
        except ValueError:
            pass
    
    # Get file count at HEAD
    file_count = 0
    result = _run_git_command(artifact_id, "ls-tree", "-r", "HEAD", "--name-only")
    if result.returncode == 0:
        file_count = len([l for l in result.stdout.strip().split("\n") if l])
    
    # Get repo size
    repo_size = _get_repo_size(artifact_id)
    
    return RepoMetadataResponse(
        name=artifact.name,
        description=artifact.description,
        artifact_id=str(artifact_id),
        git_remote_url=git_remote_url,
        clone_url=clone_url,
        default_branch="master",
        last_commit=last_commit,
        commit_count=commit_count,
        file_count=file_count,
        repo_size_bytes=repo_size,
        publish=_get_publish_config(artifact),
    )


@router.get("/{artifact_id}/repo/tree", response_model=RepoTreeResponse)
async def get_repo_tree(
    artifact_id: UUID,
    ref: str = "HEAD",
    path: str = "",
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get file tree for a repository at a given ref and path.
    
    - **ref**: Git ref (branch, tag, or commit SHA). Default: HEAD
    - **path**: Subdirectory path within the repo. Default: root
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    if artifact.type != "repo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact is not a repository"
        )
    
    if not _repo_exists(artifact_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not initialized yet"
        )
    
    # Build tree path argument
    tree_path = f"{ref}:{path}" if path else ref
    
    # Get tree listing
    result = _run_git_command(
        artifact_id,
        "ls-tree",
        "-l",  # Show sizes
        tree_path
    )
    
    if result.returncode != 0:
        # Could be invalid ref or path
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Path not found: {path} at ref {ref}"
        )
    
    items = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        # Parse ls-tree output: <mode> <type> <sha> <size>\t<name>
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        meta, name = parts
        meta_parts = meta.split()
        if len(meta_parts) < 4:
            continue
        
        item_type = meta_parts[1]  # blob or tree
        size_str = meta_parts[3] if len(meta_parts) > 3 else None
        
        item_path = f"{path}/{name}" if path else name
        
        items.append(RepoTreeItem(
            name=name,
            path=item_path,
            type=item_type,
            size=int(size_str) if size_str and item_type == "blob" else None,
        ))
    
    return RepoTreeResponse(
        ref=ref,
        items=items,
    )


@router.get("/{artifact_id}/repo/files/{file_path:path}", response_model=RepoFileResponse)
async def get_repo_file(
    artifact_id: UUID,
    file_path: str,
    ref: str = "HEAD",
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get raw file contents from a repository.
    
    - **ref**: Git ref (branch, tag, or commit SHA). Default: HEAD
    - **file_path**: Path to file within the repo
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    if artifact.type != "repo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact is not a repository"
        )
    
    if not _repo_exists(artifact_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not initialized yet"
        )
    
    # Check if path is a file (not a directory)
    result = _run_git_command(
        artifact_id,
        "cat-file",
        "-t",
        f"{ref}:{file_path}"
    )
    
    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}"
        )
    
    obj_type = result.stdout.strip()
    if obj_type != "blob":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a file: {file_path} (type: {obj_type})"
        )
    
    # Get file size
    result = _run_git_command(
        artifact_id,
        "cat-file",
        "-s",
        f"{ref}:{file_path}"
    )
    file_size = 0
    if result.returncode == 0:
        try:
            file_size = int(result.stdout.strip())
        except ValueError:
            pass
    
    # Get file contents
    result = _run_git_command(
        artifact_id,
        "show",
        f"{ref}:{file_path}"
    )
    
    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read file contents"
        )
    
    content = result.stdout
    is_binary = False
    
    # Try to detect binary content (null bytes)
    if '\x00' in content:
        is_binary = True
        content = "[Binary file - cannot display]"
    
    return RepoFileResponse(
        path=file_path,
        ref=ref,
        content=content,
        size=file_size,
        is_binary=is_binary,
    )


@router.get("/{artifact_id}/repo/commits", response_model=RepoCommitsResponse)
async def get_repo_commits(
    artifact_id: UUID,
    ref: str = "HEAD",
    limit: int = 50,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get commit history for a repository.
    
    - **ref**: Git ref (branch, tag, or commit SHA). Default: HEAD
    - **limit**: Maximum commits to return. Default: 50, Max: 200
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    if artifact.type != "repo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact is not a repository"
        )
    
    if not _repo_exists(artifact_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not initialized yet"
        )
    
    limit = min(limit, 200)
    
    result = _run_git_command(
        artifact_id,
        "log",
        ref,
        f"--max-count={limit}",
        "--format=%H|%s|%an <%ae>|%aI"
    )
    
    commits = []
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) >= 4:
                commits.append(RepoCommit(
                    hash=parts[0][:7],
                    message=parts[1],
                    author=parts[2],
                    date=parts[3],
                ))
    
    return RepoCommitsResponse(
        commits=commits,
    )


@router.get("/{artifact_id}/repo/commits/{commit_hash}", response_model=RepoCommitDetailResponse)
async def get_repo_commit_detail(
    artifact_id: UUID,
    commit_hash: str,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get detailed info for a single commit, including file diffs.

    - **commit_hash**: Full or short commit SHA
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.type != "repo":
        raise HTTPException(status_code=400, detail="Artifact is not a repository")
    if not _repo_exists(artifact_id):
        raise HTTPException(status_code=404, detail="Repository not initialized yet")

    # Validate commit exists
    result = _run_git_command(artifact_id, "cat-file", "-t", commit_hash)
    if result.returncode != 0:
        raise HTTPException(status_code=404, detail=f"Commit not found: {commit_hash}")

    # Get commit metadata
    result = _run_git_command(
        artifact_id, "log", "-1",
        "--format=%H|%s|%an <%ae>|%aI|%P", commit_hash
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise HTTPException(status_code=500, detail="Failed to read commit")

    parts = result.stdout.strip().split("|", 4)
    full_hash = parts[0]
    message = parts[1] if len(parts) > 1 else ""
    author = parts[2] if len(parts) > 2 else ""
    date = parts[3] if len(parts) > 3 else ""
    parent_hash = parts[4][:7] if len(parts) > 4 and parts[4] else None

    # Get diff stat + patch
    result = _run_git_command(
        artifact_id, "diff", "--stat-width=200", "--patch",
        f"{commit_hash}~1", commit_hash
    )
    # First commit has no parent — diff against empty tree
    if result.returncode != 0:
        result = _run_git_command(
            artifact_id, "diff", "--stat-width=200", "--patch",
            "--root", commit_hash
        )

    files = []
    total_additions = 0
    total_deletions = 0

    if result.returncode == 0 and result.stdout.strip():
        raw_diff = result.stdout
        current_file = None
        current_status = "modified"
        current_lines: list[str] = []
        current_additions = 0
        current_deletions = 0

        def _save_file():
            if current_file:
                files.append(RepoDiffFile(
                    path=current_file,
                    status=current_status,
                    additions=current_additions,
                    deletions=current_deletions,
                    patch="\n".join(current_lines),
                ))

        for line in raw_diff.split("\n"):
            if line.startswith("diff --git"):
                _save_file()
                diff_parts = line.split(" b/", 1)
                current_file = diff_parts[1] if len(diff_parts) > 1 else "unknown"
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

    return RepoCommitDetailResponse(
        hash=full_hash,
        short_hash=full_hash[:7],
        message=message,
        author=author,
        date=date,
        parent_hash=parent_hash,
        files=files,
        total_additions=total_additions,
        total_deletions=total_deletions,
    )


# ============================================================================
# Publish / Deploy Endpoints
# ============================================================================

@router.get("/{artifact_id}/publish", response_model=PublishSettingsResponse)
async def get_publish_settings(
    artifact_id: UUID,
    request: Request,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Get publishing configuration for a repo artifact."""
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact or artifact.type != "repo":
        raise HTTPException(status_code=404, detail="Repository not found")

    pub = _get_publish_config(artifact)
    return PublishSettingsResponse(
        enabled=pub.enabled,
        slug=pub.slug,
        render_mode=pub.render_mode,
        build_command=pub.build_command,
        output_dir=pub.output_dir,
        auto_deploy=pub.auto_deploy,
        allow_public_code_view=pub.allow_public_code_view,
        status=pub.status,
        last_deploy_at=pub.last_deploy_at,
        last_deploy_commit=pub.last_deploy_commit,
        site_url=_get_site_url(request, pub.slug) if pub.slug else "",
    )


@router.put("/{artifact_id}/publish", response_model=PublishSettingsResponse)
async def update_publish_settings(
    artifact_id: UUID,
    body: PublishSettingsRequest,
    request: Request,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Update publishing configuration for a repo artifact."""
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact or artifact.type != "repo":
        raise HTTPException(status_code=404, detail="Repository not found")

    updates = body.model_dump(exclude_unset=True)

    # Auto-generate slug if not provided when enabling
    if "enabled" in updates and updates["enabled"]:
        current_pub = _get_publish_config(artifact)
        if not updates.get("slug") and not current_pub.slug:
            updates["slug"] = _generate_slug(artifact.name)

    # Validate slug uniqueness if changing
    if "slug" in updates and updates["slug"]:
        slug = updates["slug"]
        if not re.match(r'^[a-z0-9][a-z0-9\-]*$', slug):
            raise HTTPException(status_code=400, detail="Slug must be lowercase alphanumeric with hyphens")
        # Check uniqueness
        existing = db.query(Artifact).filter(
            Artifact.type == "repo",
            Artifact.id != artifact_id,
        ).all()
        for other in existing:
            other_pub = (other.meta or {}).get("publish", {})
            if other_pub.get("slug") == slug:
                raise HTTPException(status_code=409, detail="Slug is already in use")

    _save_publish_config(artifact, db, updates)

    pub = _get_publish_config(artifact)
    return PublishSettingsResponse(
        enabled=pub.enabled,
        slug=pub.slug,
        render_mode=pub.render_mode,
        build_command=pub.build_command,
        output_dir=pub.output_dir,
        auto_deploy=pub.auto_deploy,
        allow_public_code_view=pub.allow_public_code_view,
        status=pub.status,
        last_deploy_at=pub.last_deploy_at,
        last_deploy_commit=pub.last_deploy_commit,
        site_url=_get_site_url(request, pub.slug) if pub.slug else "",
    )


@router.delete("/{artifact_id}/publish")
async def unpublish(
    artifact_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Unpublish a repo artifact — disable serving and remove published files."""
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact or artifact.type != "repo":
        raise HTTPException(status_code=404, detail="Repository not found")

    # Remove published files
    published_path = _get_published_path(artifact_id)
    if os.path.exists(published_path):
        shutil.rmtree(published_path)

    # Clear publish config
    meta = artifact.meta or {}
    meta["publish"] = {
        "enabled": False,
        "slug": "",
        "render_mode": "embedded",
        "build_command": "",
        "output_dir": "dist",
        "auto_deploy": True,
        "allow_public_code_view": False,
        "status": "idle",
    }
    artifact.meta = meta
    flag_modified(artifact, "meta")
    db.commit()

    return {"detail": "Site unpublished"}


@router.post("/{artifact_id}/deploy")
async def trigger_deploy(
    artifact_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Manually trigger a deploy for a repo artifact."""
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact or artifact.type != "repo":
        raise HTTPException(status_code=404, detail="Repository not found")

    pub = _get_publish_config(artifact)
    if not pub.enabled:
        raise HTTPException(status_code=400, detail="Publishing is not enabled for this repository")

    if not _repo_exists(artifact_id):
        raise HTTPException(status_code=400, detail="Repository has no content yet")

    # Queue the deploy task
    from celery_app.tasks import deploy_repo_task
    task = deploy_repo_task.delay(str(artifact_id))

    return {"task_id": task.id, "status": "queued"}


@router.get("/{artifact_id}/deploy/status", response_model=DeployStatusResponse)
async def get_deploy_status(
    artifact_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Get the current deploy status for a repo artifact."""
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    if not artifact or artifact.type != "repo":
        raise HTTPException(status_code=404, detail="Repository not found")

    pub = _get_publish_config(artifact)
    return DeployStatusResponse(
        status=pub.status,
        last_deploy_at=pub.last_deploy_at,
        last_deploy_commit=pub.last_deploy_commit,
        last_deploy_log=pub.last_deploy_log,
    )


# ============================================================================
# Internal Deploy Endpoint (called by post-receive hook)
# ============================================================================

# Internal router for post-receive hook (no auth — internal network only)
_internal_router = APIRouter(prefix="/internal", tags=["internal"])


@_internal_router.post("/deploy/{artifact_id}")
async def internal_trigger_deploy(
    artifact_id: UUID,
    body: dict = {},
    db: Session = Depends(get_db),
):
    """
    Internal endpoint called by the git post-receive hook.
    Queues a deploy task if auto_deploy is enabled.
    """
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact or artifact.type != "repo":
        return {"detail": "skipped"}

    pub = _get_publish_config(artifact)
    if not pub.enabled or not pub.auto_deploy:
        return {"detail": "skipped"}

    ref = body.get("ref", "")

    # Queue the deploy task
    from celery_app.tasks import deploy_repo_task
    task = deploy_repo_task.delay(str(artifact_id), ref=ref)

    return {"task_id": task.id, "status": "queued"}
