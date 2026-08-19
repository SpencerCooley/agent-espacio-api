"""
Folder controller - search within folder scope.

Searches folder names, asset names, and artifact names within a folder
and all its descendants, or across a multi-root scope forest.
"""
from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy.orm import Session

from models.folder import Folder


def _descendant_ids(db: Session, root_ids: List[UUID]) -> List[UUID]:
    """BFS collect root_ids plus all descendants."""
    if not root_ids:
        return []
    collected: list[UUID] = list(root_ids)
    seen: set[UUID] = set(root_ids)
    queue = list(root_ids)
    while queue:
        children = db.query(Folder).filter(Folder.parent_id.in_(queue)).all()
        queue = []
        for child in children:
            if child.id not in seen:
                seen.add(child.id)
                collected.append(child.id)
                queue.append(child.id)
    return collected


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
    target = db.query(Folder).filter(Folder.id == folder_id).first()
    if not target:
        return [], [], []

    descendant_ids = _descendant_ids(db, [target.id])
    return _search_within_folder_ids(db, descendant_ids, query, limit)


def search_within_folder_ids(
    db: Session,
    folder_ids: Optional[Set[UUID]],
    query: str,
    limit: int = 50,
) -> tuple[List[Folder], list, list]:
    """
    Search within an explicit set of folder IDs (scope forest).

    folder_ids=None means unrestricted (search entire tree, excluding root).
    folder_ids=empty set means no access → empty results.
    """
    if folder_ids is not None and len(folder_ids) == 0:
        return [], [], []

    if folder_ids is None:
        # Unrestricted: all non-root folders
        all_ids = [
            row.id
            for row in db.query(Folder.id).filter(Folder.is_root == False).all()
        ]
        return _search_within_folder_ids(db, all_ids, query, limit)

    return _search_within_folder_ids(db, list(folder_ids), query, limit)


def _search_within_folder_ids(
    db: Session,
    descendant_ids: List[UUID],
    query: str,
    limit: int,
) -> tuple[List[Folder], list, list]:
    if not descendant_ids:
        return [], [], []

    search_pattern = f"%{query}%"

    folder_results = db.query(Folder).filter(
        Folder.id.in_(descendant_ids),
        Folder.is_root == False,
        Folder.name.ilike(search_pattern)
    ).order_by(Folder.name).limit(limit).all()

    from models.asset import Asset
    asset_results = db.query(Asset).filter(
        Asset.folder_id.in_(descendant_ids),
        Asset.name.ilike(search_pattern)
    ).order_by(Asset.name).limit(limit).all()

    from models.artifact import Artifact
    artifact_results = db.query(Artifact).filter(
        Artifact.folder_id.in_(descendant_ids),
        Artifact.name.ilike(search_pattern)
    ).order_by(Artifact.name).limit(limit).all()

    return folder_results, asset_results, artifact_results
