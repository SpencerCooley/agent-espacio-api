"""
Repository router.

Endpoints for browsing git repository artifacts:
- GET /artifacts/{id}/repo - Repo metadata
- GET /artifacts/{id}/repo/tree - File tree
- GET /artifacts/{id}/repo/files/{path} - Raw file contents
- GET /artifacts/{id}/repo/commits - Commit history
"""
import os
import subprocess
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
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


# ============================================================================
# Pydantic Response Models
# ============================================================================

class RepoMetadataResponse(BaseModel):
    artifact_id: str = Field(..., description="Artifact UUID")
    git_remote_url: str = Field(..., description="Git SSH remote URL")
    default_branch: str = Field(default="master", description="Default branch name")
    last_commit: Optional[Dict[str, Any]] = Field(None, description="Last commit info")
    commit_count: int = Field(default=0, description="Total commits")
    file_count: int = Field(default=0, description="Files at HEAD")
    repo_size_bytes: int = Field(default=0, description="Size of bare repo on disk")


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


class RepoFileResponse(BaseModel):
    path: str = Field(..., description="File path")
    ref: str = Field(..., description="Git ref")
    content: str = Field(..., description="Raw file contents as text")
    size: int = Field(..., description="File size in bytes")
    is_binary: bool = Field(default=False, description="Whether file is binary")


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
    
    # Check if repo exists on disk
    if not _repo_exists(artifact_id):
        return RepoMetadataResponse(
            artifact_id=str(artifact_id),
            git_remote_url=git_remote_url,
            default_branch="master",
            last_commit=None,
            commit_count=0,
            file_count=0,
            repo_size_bytes=0,
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
        artifact_id=str(artifact_id),
        git_remote_url=git_remote_url,
        default_branch="master",
        last_commit=last_commit,
        commit_count=commit_count,
        file_count=file_count,
        repo_size_bytes=repo_size,
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
