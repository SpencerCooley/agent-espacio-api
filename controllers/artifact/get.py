"""
Artifact controller - get artifact.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.artifact import Artifact


def get_artifact(db: Session, artifact_id: UUID) -> Optional[Artifact]:
    """
    Get an artifact by ID.

    Args:
        db: Database session
        artifact_id: Artifact UUID

    Returns:
        Artifact object if found, None otherwise
    """
    return db.query(Artifact).filter(Artifact.id == artifact_id).first()
