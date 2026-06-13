"""
Artifact controller - delete artifact.
"""
from sqlalchemy.orm import Session

from models.artifact import Artifact


def delete_artifact(
    db: Session,
    artifact: Artifact
) -> None:
    """
    Delete an artifact from the database.

    Args:
        db: Database session
        artifact: Artifact object to delete
    """
    from ._sync_links import remove_artifact_from_all_links
    remove_artifact_from_all_links(db, artifact)

    db.delete(artifact)
    db.commit()
