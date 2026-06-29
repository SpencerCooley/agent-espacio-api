"""
Artifact composition controller.

Handles resolving and returning composer artifacts with all referenced sub-items
(artifacts and assets).
"""
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.artifact import Artifact
from models.asset import Asset


def _serialize_item(item) -> Optional[Dict[str, Any]]:
    """Serialize an Artifact or Asset object into a plain dict."""
    if not item:
        return None
    if isinstance(item, Artifact):
        return {
            "id": str(item.id),
            "name": item.name,
            "type": item.type,
            "description": item.description,
            "content": item.content,
            "folder_id": str(item.folder_id),
            "is_public": item.is_public,
            "public_magic_id": str(item.public_magic_id) if item.public_magic_id else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "created_by_id": item.created_by_id,
        }
    if isinstance(item, Asset):
        return {
            "id": str(item.id),
            "name": item.name,
            "mime_type": item.mime_type,
            "size_bytes": item.size_bytes,
            "human_readable_size": item.human_readable_size,
            "is_image": item.is_image,
            "is_public": item.is_public,
            "public_magic_id": str(item.public_magic_id) if item.public_magic_id else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
    return None


def _serialize_composer(composer: Artifact) -> Dict[str, Any]:
    """Serialize a composer artifact into a plain dict."""
    return {
        "id": str(composer.id),
        "name": composer.name,
        "type": composer.type,
        "description": composer.description,
        "content": composer.content,
        "folder_id": str(composer.folder_id),
        "is_public": composer.is_public,
        "public_magic_id": str(composer.public_magic_id) if composer.public_magic_id else None,
        "created_at": composer.created_at.isoformat() if composer.created_at else None,
        "updated_at": composer.updated_at.isoformat() if composer.updated_at else None,
        "created_by_id": composer.created_by_id,
    }


def resolve_composition(db: Session, composer: Artifact) -> Dict[str, Any]:
    """
    Resolve a composer artifact's sections into full artifact/asset data.

    Fetches all referenced items (both artifacts and assets) in a single query
    and returns them alongside the section metadata (caption).

    Args:
        db: Database session
        composer: The composer artifact

    Returns:
        Dict with 'composer' (dict) and 'sections' (list of resolved sections with item as dict)
    """
    content = composer.content or {}
    sections_data = content.get("sections", [])

    if not sections_data:
        return {
            "composer": _serialize_composer(composer),
            "sections": [],
        }

    # Collect all IDs from sections
    all_ids = []
    for section in sections_data:
        if isinstance(section, dict):
            item_id = section.get("artifact_id")
            if item_id:
                try:
                    all_ids.append(UUID(str(item_id)))
                except (ValueError, TypeError):
                    continue

    # Fetch all referenced artifacts in one query
    artifacts = {}
    if all_ids:
        arts = db.query(Artifact).filter(Artifact.id.in_(all_ids)).all()
        for art in arts:
            artifacts[str(art.id)] = art

    # Fetch remaining IDs from assets
    asset_ids = [id for id in all_ids if str(id) not in artifacts]
    assets = {}
    if asset_ids:
        asts = db.query(Asset).filter(Asset.id.in_(asset_ids)).all()
        for ast in asts:
            assets[str(ast.id)] = ast

    # Build resolved sections preserving order
    resolved_sections = []
    for section in sections_data:
        if not isinstance(section, dict):
            continue
        item_id = section.get("artifact_id")
        caption = section.get("caption")
        item = (artifacts.get(str(item_id)) or assets.get(str(item_id))) if item_id else None

        resolved_sections.append({
            "item": _serialize_item(item),
            "caption": caption,
            "artifact_id": str(item_id) if item_id else None,
        })

    return {
        "composer": _serialize_composer(composer),
        "sections": resolved_sections,
    }


def resolve_public_composition(db: Session, composer: Artifact) -> Dict[str, Any]:
    """
    Resolve a public composer, only including publicly accessible sub-items.

    Sub-items that are not public are omitted (replaced with None in the section).

    Args:
        db: Database session
        composer: The composer artifact (must be public)

    Returns:
        Dict with 'composer' (dict) and 'sections' (filtered to public-only with item as dict)
    """
    from controllers.public import is_artifact_public, is_asset_public

    content = composer.content or {}
    sections_data = content.get("sections", [])

    if not sections_data:
        return {
            "composer": _serialize_composer(composer),
            "sections": [],
        }

    # Collect all IDs
    all_ids = []
    for section in sections_data:
        if isinstance(section, dict):
            item_id = section.get("artifact_id")
            if item_id:
                try:
                    all_ids.append(UUID(str(item_id)))
                except (ValueError, TypeError):
                    continue

    # Fetch all referenced artifacts
    artifacts = {}
    if all_ids:
        arts = db.query(Artifact).filter(Artifact.id.in_(all_ids)).all()
        for art in arts:
            artifacts[str(art.id)] = art

    # Fetch remaining IDs from assets
    asset_ids = [id for id in all_ids if str(id) not in artifacts]
    assets = {}
    if asset_ids:
        asts = db.query(Asset).filter(Asset.id.in_(asset_ids)).all()
        for ast in asts:
            assets[str(ast.id)] = ast

    # Build resolved sections, filtering by public access
    resolved_sections = []
    for section in sections_data:
        if not isinstance(section, dict):
            continue
        item_id = section.get("artifact_id")
        caption = section.get("caption")
        item = (artifacts.get(str(item_id)) or assets.get(str(item_id))) if item_id else None

        # Check if item is public
        is_public = False
        if item:
            if isinstance(item, Asset):
                is_public = is_asset_public(db, item)
            else:
                is_public = is_artifact_public(db, item)

        resolved_sections.append({
            "item": _serialize_item(item) if is_public else None,
            "caption": caption,
            "artifact_id": str(item_id) if item_id else None,
        })

    return {
        "composer": _serialize_composer(composer),
        "sections": resolved_sections,
    }
