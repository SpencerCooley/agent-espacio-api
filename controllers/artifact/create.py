"""
Artifact controller - create artifact.
"""
import os
import subprocess
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.artifact import Artifact
from models.folder import Folder
from models.user import User


STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
REPOS_DIR = os.path.join(STORAGE_PATH, "repos")


def _init_bare_repo(artifact_id: UUID) -> None:
    """Initialize a bare git repository for a repo artifact."""
    repo_path = os.path.join(REPOS_DIR, f"{artifact_id}.git")
    os.makedirs(repo_path, exist_ok=True)
    subprocess.run(
        ["git", "init", "--bare", repo_path],
        check=True,
        capture_output=True,
    )
    # Create post-receive hook placeholder for Phase 2 build trigger
    hook_path = os.path.join(repo_path, "hooks", "post-receive")
    with open(hook_path, "w") as f:
        f.write("#!/bin/bash\n# Phase 2: trigger build here\n")
    os.chmod(hook_path, 0o755)


def _remove_bare_repo(artifact_id: UUID) -> None:
    """Remove a bare git repository when its artifact is deleted."""
    import shutil
    repo_path = os.path.join(REPOS_DIR, f"{artifact_id}.git")
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)


def create_artifact(
    db: Session,
    name: str,
    type: str,
    content: dict,
    folder_id: UUID,
    created_by: Optional[User] = None,
    description: Optional[str] = None,
) -> Artifact:
    """
    Create a new artifact.

    Args:
        db: Database session
        name: Artifact display name
        type: Artifact type key (e.g., 'note')
        content: Artifact content as a JSON-compatible dict
        folder_id: Parent folder ID
        created_by: User creating the artifact (None for API-key/agent created)
        description: Optional readme/description for AI context

    Returns:
        Artifact object

    Raises:
        ValueError: If folder not found
    """
    # Validate folder exists
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise ValueError("Parent folder not found")

    # Validate composer content (no nested composers)
    if type == "composer":
        from .validate import validate_no_nested_composers
        validate_no_nested_composers(db, content)

    artifact = Artifact(
        name=name,
        type=type,
        description=description,
        content=content,
        folder_id=folder_id,
        created_by_id=created_by.id if created_by else None,
    )

    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    # Initialize bare git repo for repo artifacts
    if type == "repo":
        try:
            _init_bare_repo(artifact.id)
        except Exception:
            # If repo init fails, still return the artifact (user can retry or debug)
            pass

    from ._sync_links import sync_artifact_asset_links
    sync_artifact_asset_links(db, artifact)

    return artifact
