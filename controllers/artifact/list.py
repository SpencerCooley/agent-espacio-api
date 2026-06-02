"""
Artifact controller - list artifacts.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.artifact import Artifact


def list_artifacts(
    db: Session,
    folder_id: Optional[UUID] = None,
    type: Optional[str] = None,
) -> List[Artifact]:
    """
    List artifacts with optional filters.

    Args:
        db: Database session
        folder_id: Filter by parent folder
        type: Filter by artifact type key

    Returns:
        List of Artifact objects
    """
    query = db.query(Artifact)

    if folder_id is not None:
        query = query.filter(Artifact.folder_id == folder_id)

    if type:
        query = query.filter(Artifact.type == type)

    return query.order_by(Artifact.name).all()


def list_all_artifacts(db: Session) -> List[Artifact]:
    """
    List all artifacts, ordered by name.

    Args:
        db: Database session

    Returns:
        List of Artifact objects
    """
    return db.query(Artifact).order_by(Artifact.name).all()


def count_artifacts_in_folder(db: Session, folder_id: Optional[UUID] = None) -> int:
    """
    Count artifacts in a specific folder.

    Args:
        db: Database session
        folder_id: Folder ID

    Returns:
        Number of artifacts
    """
    query = db.query(Artifact)

    if folder_id is not None:
        query = query.filter(Artifact.folder_id == folder_id)

    return query.count()
