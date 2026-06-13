"""
Artifact controller - share toggle.
"""
from uuid import uuid4, UUID

from sqlalchemy.orm import Session

from models.artifact import Artifact


def toggle_artifact_share(db: Session, artifact: Artifact) -> Artifact:
    """
    Toggle an artifact's public sharing status.
    
    If currently private, makes it public and generates a public_magic_id.
    If currently public, makes it private and clears the public_magic_id.
    
    Args:
        db: Database session
        artifact: Artifact to toggle
        
    Returns:
        Updated artifact object
    """
    if artifact.is_public:
        artifact.is_public = False
        artifact.public_magic_id = None
    else:
        artifact.is_public = True
        artifact.public_magic_id = uuid4()
    
    db.commit()
    db.refresh(artifact)
    return artifact
