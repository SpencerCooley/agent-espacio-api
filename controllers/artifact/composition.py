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
from models.profile import Profile


def _resolve_author(db: Session, author_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Resolve an author_id to a public profile.
    
    Args:
        db: Database session
        author_id: User ID string
        
    Returns:
        Dict with user_id, display_name, avatar_url or None if not found
    """
    if not author_id:
        return None
    
    try:
        user_id = int(author_id)
    except (ValueError, TypeError):
        return None
    
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return None
    
    # Use derivative avatar URLs
    avatar_url = None
    if profile.avatar_user_id:
        from controllers.profile.avatar import get_avatar_url
        avatar_url = get_avatar_url(profile.avatar_user_id, size=128)
    
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "avatar_url": avatar_url,
    }


def _resolve_public_author(db: Session, author_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Resolve an author_id to a public profile for public-facing responses.
    
    Args:
        db: Database session
        author_id: User ID string
        
    Returns:
        Dict with user_id, display_name, avatar_url or None if not found
    """
    if not author_id:
        return None
    
    try:
        user_id = int(author_id)
    except (ValueError, TypeError):
        return None
    
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return None
    
    # Use derivative avatar URLs (same for public view)
    avatar_url = None
    if profile.avatar_user_id:
        from controllers.profile.avatar import get_avatar_url
        avatar_url = get_avatar_url(profile.avatar_user_id, size=128)
    
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "avatar_url": avatar_url,
    }


def _serialize_item(item, include_internal: bool = True) -> Optional[Dict[str, Any]]:
    """
    Serialize an Artifact or Asset object into a plain dict.

    When include_internal is False (public-facing responses), internal
    bookkeeping fields (folder_id, created_by_id) are omitted.
    """
    if not item:
        return None
    if isinstance(item, Artifact):
        d = {
            "id": str(item.id),
            "name": item.name,
            "type": item.type,
            "description": item.description,
            "content": item.content,
            "is_public": item.is_public,
            "public_magic_id": str(item.public_magic_id) if item.public_magic_id else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
        if include_internal:
            d["folder_id"] = str(item.folder_id)
            d["created_by_id"] = item.created_by_id
        return d
    if isinstance(item, Asset):
        d = {
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
        if include_internal:
            d["folder_id"] = str(item.folder_id) if item.folder_id else None
            d["created_by_id"] = item.created_by_id
        return d
    return None


def _serialize_composer(composer: Artifact, include_internal: bool = True, public_urls: bool = False, author: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Serialize a composer artifact into a plain dict.

    When include_internal is False (public-facing responses), internal
    bookkeeping fields (folder_id, created_by_id) are omitted.

    When public_urls is True, cover_url uses public /public/assets/... URLs
    that never expire (good for SSR). When False, uses signed URLs for
    authenticated workspace views.
    """
    meta = composer.meta or {}
    content = composer.content or {}
    cover_asset_id = meta.get("cover_asset_id")
    cover_url = None
    if cover_asset_id:
        try:
            if public_urls:
                from controllers.asset.signed_url import _build_public_url
                cover_url = _build_public_url(cover_asset_id, size=512)
            else:
                from controllers.asset.signed_url import generate_signed_url
                cover_url = generate_signed_url(cover_asset_id, size=512, expiry_seconds=3600)
        except Exception:
            pass

    # Determine published_at (override or fallback to created_at)
    published_at = content.get("published_at")
    if not published_at:
        published_at = composer.created_at.isoformat() if composer.created_at else None

    d = {
        "id": str(composer.id),
        "name": composer.name,
        "type": composer.type,
        "description": composer.description,
        "content": composer.content,
        "meta": meta,
        "cover_url": cover_url,
        "is_public": composer.is_public,
        "public_magic_id": str(composer.public_magic_id) if composer.public_magic_id else None,
        "created_at": composer.created_at.isoformat() if composer.created_at else None,
        "updated_at": composer.updated_at.isoformat() if composer.updated_at else None,
        "published_at": published_at,
        "author": author,
    }
    if include_internal:
        d["folder_id"] = str(composer.folder_id)
        d["created_by_id"] = composer.created_by_id
    return d


def resolve_composition(
    db: Session,
    composer: Artifact,
    signed: bool = False,
) -> Dict[str, Any]:
    """
    Resolve a composer artifact's sections into full artifact/asset data.

    Fetches all referenced items (both artifacts and assets) in a single query
    and returns them alongside the section metadata (caption).

    Args:
        db: Database session
        composer: The composer artifact
        signed: When True, enrich each section artifact's content with
            time-bound signed asset URLs (for preview mode — images load
            even when nested assets are outside the caller's folder scope).

    Returns:
        Dict with 'composer' (dict) and 'sections' (list of resolved sections with item as dict)
    """
    import copy
    from controllers.asset.signed_url import enrich_content_with_signed_urls

    content = composer.content or {}
    sections_data = content.get("sections", [])

    # Resolve author
    author_id = content.get("author_id")
    author = _resolve_author(db, author_id)

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

        item_dict = _serialize_item(item)
        if signed and item_dict and isinstance(item, Artifact) and item_dict.get("content"):
            item_dict["content"] = enrich_content_with_signed_urls(
                copy.deepcopy(item_dict["content"]),
                expiry_seconds=3600,
            )

        resolved_sections.append({
            "item": item_dict,
            "caption": caption,
            "artifact_id": str(item_id) if item_id else None,
        })

    return {
        "composer": _serialize_composer(composer, author=author),
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

    # Resolve author for public view
    author_id = content.get("author_id")
    author = _resolve_public_author(db, author_id)

    if not sections_data:
        return {
            "composer": _serialize_composer(composer, include_internal=False),
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
    from controllers.asset.signed_url import enrich_content_with_public_urls

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

        if is_public and item and isinstance(item, Artifact):
            # Enrich artifact content with public URLs for embedded assets
            import copy
            item_dict = _serialize_item(item, include_internal=False)
            item_dict["content"] = enrich_content_with_public_urls(
                copy.deepcopy(item.content or {}), size=512
            )
        else:
            item_dict = _serialize_item(item, include_internal=False) if is_public else None

        resolved_sections.append({
            "item": item_dict,
            "caption": caption,
            "artifact_id": str(item_id) if item_id else None,
        })

    return {
        "composer": _serialize_composer(composer, include_internal=False, public_urls=True, author=author),
        "sections": resolved_sections,
    }
