"""
Artifact controller - delete artifact.
"""
from sqlalchemy.orm import Session

from models.artifact import Artifact
from controllers.artifact.create import _remove_bare_repo


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

    # Clean up bare git repo if this is a repo artifact
    if artifact.type == "repo":
        try:
            _remove_bare_repo(artifact.id)
        except Exception:
            pass  # Best effort cleanup

    db.delete(artifact)
    db.commit()
