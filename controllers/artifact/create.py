"""
Artifact controller - create artifact.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.artifact import Artifact
from models.folder import Folder
from models.user import User


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

    return artifact
