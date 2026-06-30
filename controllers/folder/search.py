"""
Folder controller - search within folder scope.

Searches folder names, asset names, and artifact names within a folder
and all its descendants.
"""
from typing import List
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.folder import Folder


def search_folder_scope(
    db: Session,
    folder_id: UUID,
    query: str,
    limit: int = 50
) -> tuple[List[Folder], list, list]:
    """
    Search for items by name within a folder and all its subfolders.

    Args:
        db: Database session
        folder_id: The folder to search within (including descendants)
        query: Search term (case-insensitive partial match)
        limit: Maximum results per kind (total max 3 * limit)

    Returns:
        Tuple of (matching_folders, matching_assets, matching_artifacts)
    """
    # Get the target folder to extract its path
    target = db.query(Folder).filter(Folder.id == folder_id).first()
    if not target:
        return [], [], []

    # Find all descendant folder IDs recursively (including self)
    # We walk the actual parent_id tree instead of relying on the path column,
    # which guarantees we find every descendant at any nesting depth.
    descendant_ids: list[UUID] = []
    queue = [target.id]
    while queue:
        children = db.query(Folder).filter(Folder.parent_id.in_(queue)).all()
        queue = [c.id for c in children if c.id not in descendant_ids]
        descendant_ids.extend(queue)

    # Always include the target folder itself
    if target.id not in descendant_ids:
        descendant_ids.append(target.id)

    if not descendant_ids:
        return [], [], []

    search_pattern = f"%{query}%"

    # Search folders within scope (name match, exclude root)
    folder_results = db.query(Folder).filter(
        Folder.id.in_(descendant_ids),
        Folder.is_root == False,
        Folder.name.ilike(search_pattern)
    ).order_by(Folder.name).limit(limit).all()

    # Search assets within scope
    from models.asset import Asset
    asset_results = db.query(Asset).filter(
        Asset.folder_id.in_(descendant_ids),
        Asset.name.ilike(search_pattern)
    ).order_by(Asset.name).limit(limit).all()

    # Search artifacts within scope
    from models.artifact import Artifact
    artifact_results = db.query(Artifact).filter(
        Artifact.folder_id.in_(descendant_ids),
        Artifact.name.ilike(search_pattern)
    ).order_by(Artifact.name).limit(limit).all()

    return folder_results, asset_results, artifact_results
