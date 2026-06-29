"""
Artifact controller - update artifact.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.artifact import Artifact
from models.folder import Folder


def update_artifact(
    db: Session,
    artifact: Artifact,
    name: Optional[str] = None,
    type: Optional[str] = None,
    description: Optional[str] = None,
    content: Optional[dict] = None,
    folder_id: Optional[UUID] = None,
) -> Artifact:
    """
    Update an artifact's fields.

    Args:
        db: Database session
        artifact: Artifact object to update
        name: New display name
        type: New artifact type key
        description: New description
        content: New content JSONB
        folder_id: New parent folder ID (for moving)

    Returns:
        Updated artifact object

    Raises:
        ValueError: If new folder not found
    """
    # Update name if provided
    if name is not None:
        artifact.name = name

    # Update type if provided
    if type is not None:
        artifact.type = type

    # Update description if provided
    if description is not None:
        artifact.description = description

    # Capture old linked_asset_ids before content changes
    from ._sync_links import extract_linked_asset_ids
    old_linked_ids = extract_linked_asset_ids(artifact.content)

    # Update content if provided
    if content is not None:
        artifact.content = content

    # Validate composer content (no nested composers)
    if artifact.type == "composer":
        from .validate import validate_no_nested_composers
        validate_no_nested_composers(db, artifact.content)

    # Move to new folder if provided
    if folder_id is not None and folder_id != artifact.folder_id:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            raise ValueError("Target folder not found")
        artifact.folder_id = folder_id

    db.commit()
    db.refresh(artifact)

    from ._sync_links import sync_artifact_asset_links
    sync_artifact_asset_links(db, artifact, old_linked_ids)

    return artifact
