"""
Artifact content validation utilities.

Provides shared validation functions for artifact create/update operations.
"""
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session

from models.artifact import Artifact


def validate_no_nested_composers(db: Session, content: Optional[Dict[str, Any]]) -> None:
    """
    Validate that a composer artifact does not reference another composer.

    A composition cannot contain another composition. Users should use a note
    with a hyperlink if they want to link to another composition.

    Args:
        db: Database session
        content: Artifact content dict

    Raises:
        ValueError: If any referenced artifact is a composer
    """
    if not content or not isinstance(content, dict):
        return

    sections = content.get("sections", [])
    if not isinstance(sections, list):
        return

    artifact_ids = []
    for section in sections:
        if isinstance(section, dict):
            artifact_id = section.get("artifact_id")
            if artifact_id:
                try:
                    UUID(str(artifact_id))
                    artifact_ids.append(str(artifact_id))
                except (ValueError, TypeError):
                    continue

    if not artifact_ids:
        return

    # Check if any referenced artifact is a composer
    referenced = db.query(Artifact).filter(Artifact.id.in_(artifact_ids)).all()
    for art in referenced:
        if art.type == "composer":
            raise ValueError(
                f"Cannot reference composition '{art.name}' inside another composition. "
                "Use a note with a hyperlink to link to other compositions."
            )
