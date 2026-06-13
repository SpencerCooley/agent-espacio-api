"""
Internal helper to sync linked_asset_ids between artifacts and assets.

When an artifact's content.linked_asset_ids changes, this updates
each linked asset's file_meta.linked_artifact_ids accordingly.
Maintains bidirectional reference integrity without needing a join table.
"""

from uuid import UUID
from sqlalchemy.orm import Session

from models.asset import Asset
from models.artifact import Artifact


def extract_linked_asset_ids(content: dict | None) -> set[str]:
    """Extract linked_asset_ids from artifact content."""
    if not content or not isinstance(content, dict):
        return set()
    raw = content.get("linked_asset_ids", [])
    if not isinstance(raw, list):
        return set()
    return {str(aid) for aid in raw if aid}


def sync_artifact_asset_links(
    db: Session,
    artifact: Artifact,
    old_linked_ids: set[str] | None = None,
) -> None:
    """
    Sync artifact-to-asset links after creation or update.

    Adds/removes this artifact's ID from each linked asset's
    file_meta.linked_artifact_ids based on the diff.
    """
    new_ids = extract_linked_asset_ids(artifact.content)
    old_ids = old_linked_ids or set()

    added = new_ids - old_ids
    removed = old_ids - new_ids

    artifact_id_str = str(artifact.id)

    if added:
        assets = db.query(Asset).filter(Asset.id.in_([UUID(aid) for aid in added])).all()
        for asset in assets:
            if not asset.file_meta:
                asset.file_meta = {}
            linked = asset.file_meta.get("linked_artifact_ids", [])
            if artifact_id_str not in linked:
                linked.append(artifact_id_str)
            asset.file_meta["linked_artifact_ids"] = linked

    if removed:
        assets = db.query(Asset).filter(Asset.id.in_([UUID(aid) for aid in removed])).all()
        for asset in assets:
            if asset.file_meta and "linked_artifact_ids" in asset.file_meta:
                linked = asset.file_meta["linked_artifact_ids"]
                if artifact_id_str in linked:
                    linked.remove(artifact_id_str)
                asset.file_meta["linked_artifact_ids"] = linked

    if added or removed:
        db.commit()


def remove_artifact_from_all_links(
    db: Session,
    artifact: Artifact,
) -> None:
    """
    Remove this artifact's ID from all assets it was linked to.

    Called when an artifact is deleted.
    """
    linked_ids = extract_linked_asset_ids(artifact.content)
    if not linked_ids:
        return

    artifact_id_str = str(artifact.id)

    assets = db.query(Asset).filter(Asset.id.in_([UUID(aid) for aid in linked_ids])).all()
    for asset in assets:
        if asset.file_meta and "linked_artifact_ids" in asset.file_meta:
            linked = asset.file_meta["linked_artifact_ids"]
            if artifact_id_str in linked:
                linked.remove(artifact_id_str)
            asset.file_meta["linked_artifact_ids"] = linked

    if assets:
        db.commit()
