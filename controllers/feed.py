"""
Feed controller.

Handles curated public feed operations.

Behavior:
- GET /feed (no tag)     → strictly curated main feed (only items in feed_items table)
- GET /feed?tag=travel   → open tag discovery (any public composer with that tag,
                           regardless of whether it's in the main feed)
"""
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.feed_item import FeedItem
from models.artifact import Artifact
from controllers.public import is_artifact_public
from controllers.settings import get_public_theme
from controllers.themes import get_public_theme_definition
from controllers.asset.signed_url import generate_signed_url


def _artifact_to_feed_dict(artifact: Artifact, sort_order: Optional[int] = None, featured_level: Optional[int] = None) -> Dict[str, Any]:
    """Serialize an artifact into a feed item dict."""
    meta = artifact.meta or {}
    cover_asset_id = meta.get("cover_asset_id")
    cover_url = None
    if cover_asset_id:
        try:
            cover_url = generate_signed_url(cover_asset_id, size=512, expiry_seconds=3600)
        except Exception:
            pass

    return {
        "id": str(artifact.id),
        "name": artifact.name,
        "description": artifact.description,
        "type": artifact.type,
        "public_magic_id": str(artifact.public_magic_id) if artifact.public_magic_id else None,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        "updated_at": artifact.updated_at.isoformat() if artifact.updated_at else None,
        "meta": meta,
        "sort_order": sort_order,
        "featured_level": featured_level,
        "cover_url": cover_url,
    }


def list_feed_items(
    db: Session,
    tag: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    List public feed items.

    Two modes:
    1. No tag provided → curated main feed. Only artifacts explicitly added
        to feed_items appear. Featured items (featured_level 1, 2, 3) are
        returned first ordered by featured_level ASC. Remaining items are
        ordered by sort_order DESC, updated_at DESC.
    2. Tag provided    → open tag discovery. Any publicly accessible composer
       with the tag in meta.tags appears. Ordered by updated_at DESC.
       Does NOT require the artifact to be in feed_items.

    Returns:
    {
        "items": [...],
        "total": int,
        "has_more": bool,
        "public_theme": {...},
    }
    """
    items = []

    if tag:
        # --- Tag mode: open discovery, no feed_items join ---
        candidates = (
            db.query(Artifact)
            .filter(Artifact.type == "composer")
            .filter(Artifact.meta.op("?")(tag))
            .order_by(desc(Artifact.updated_at))
            .offset(offset)
            .limit(limit + 10)
            .all()
        )

        for artifact in candidates:
            if is_artifact_public(db, artifact):
                items.append(_artifact_to_feed_dict(artifact))
            if len(items) >= limit:
                break

    else:
        # --- Main feed mode: curated via feed_items with featured slots ---

        # Featured items first (slots 1, 2, 3)
        featured_candidates = (
            db.query(FeedItem, Artifact)
            .join(Artifact, FeedItem.artifact_id == Artifact.id)
            .filter(Artifact.type == "composer")
            .filter(FeedItem.featured_level.in_([1, 2, 3]))
            .order_by(FeedItem.featured_level.asc())
            .all()
        )

        for feed_item, artifact in featured_candidates:
            if is_artifact_public(db, artifact):
                items.append(_artifact_to_feed_dict(
                    artifact,
                    sort_order=feed_item.sort_order,
                    featured_level=feed_item.featured_level,
                ))
            if len(items) >= limit:
                break

        # Latest items (not featured) ordered by existing sort rules
        if len(items) < limit:
            remaining = limit - len(items)
            latest_candidates = (
                db.query(FeedItem, Artifact)
                .join(Artifact, FeedItem.artifact_id == Artifact.id)
                .filter(Artifact.type == "composer")
                .filter(FeedItem.featured_level == None)
                .order_by(FeedItem.sort_order.desc(), FeedItem.updated_at.desc())
                .offset(offset)
                .limit(remaining + 10)
                .all()
            )

            for feed_item, artifact in latest_candidates:
                if is_artifact_public(db, artifact):
                    items.append(_artifact_to_feed_dict(
                        artifact,
                        sort_order=feed_item.sort_order,
                        featured_level=feed_item.featured_level,
                    ))
                if len(items) >= limit:
                    break

    has_more = len(items) == limit  # conservative

    # Resolve public theme
    public_theme_pref = get_public_theme(db)
    public_theme_definition = get_public_theme_definition(
        db, public_theme_pref['theme_id'], public_theme_pref['mode']
    ) if public_theme_pref['theme_id'] else None
    public_theme_response = {
        "theme_id": public_theme_pref['theme_id'],
        "mode": public_theme_pref['mode'],
        "definition": public_theme_definition,
    }

    return {
        "items": items,
        "total": len(items),
        "has_more": has_more,
        "public_theme": public_theme_response,
    }


def add_to_feed(db: Session, artifact_id: UUID) -> FeedItem:
    """
    Add an artifact to the curated main feed.

    Args:
        db: Database session
        artifact_id: Artifact UUID

    Returns:
        The created or existing FeedItem
    """
    existing = db.query(FeedItem).filter(FeedItem.artifact_id == artifact_id).first()
    if existing:
        return existing

    # Auto-publish the artifact so it has a public_magic_id for feed links
    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if artifact:
        if not artifact.is_public:
            artifact.is_public = True
        if not artifact.public_magic_id:
            artifact.public_magic_id = uuid4()
        db.commit()
        db.refresh(artifact)

    # Determine next sort_order
    max_sort = db.query(FeedItem).order_by(desc(FeedItem.sort_order)).first()
    next_sort = (max_sort.sort_order + 1) if max_sort else 0

    feed_item = FeedItem(artifact_id=artifact_id, sort_order=next_sort)
    db.add(feed_item)
    db.commit()
    db.refresh(feed_item)
    return feed_item


def remove_from_feed(db: Session, artifact_id: UUID) -> bool:
    """
    Remove an artifact from the curated main feed.

    Args:
        db: Database session
        artifact_id: Artifact UUID

    Returns:
        True if removed, False if not found
    """
    feed_item = db.query(FeedItem).filter(FeedItem.artifact_id == artifact_id).first()
    if not feed_item:
        return False

    db.delete(feed_item)
    db.commit()
    return True


def reorder_feed_item(db: Session, artifact_id: UUID, new_sort_order: int) -> Optional[FeedItem]:
    """
    Update the sort_order of a feed item.

    Args:
        db: Database session
        artifact_id: Artifact UUID
        new_sort_order: New sort order integer

    Returns:
        Updated FeedItem or None if not found
    """
    feed_item = db.query(FeedItem).filter(FeedItem.artifact_id == artifact_id).first()
    if not feed_item:
        return None

    feed_item.sort_order = new_sort_order
    db.commit()
    db.refresh(feed_item)
    return feed_item


def set_featured_level(db: Session, artifact_id: UUID, level: Optional[int]) -> Optional[FeedItem]:
    """
    Set or clear the featured level for a feed item.

    Featured levels are exclusive slots: 1, 2, or 3. Setting a new item to an
    occupied slot bumps the existing occupant to None (not featured / X).
    Passing 0 or None clears the featured level.

    Args:
        db: Database session
        artifact_id: Artifact UUID
        level: 1, 2, 3 to feature, or 0/None to clear

    Returns:
        Updated FeedItem or None if not found
    """
    feed_item = db.query(FeedItem).filter(FeedItem.artifact_id == artifact_id).first()
    if not feed_item:
        return None

    # Normalize: 0 or None means "not featured" (X)
    normalized_level = None if level is None or level == 0 else level

    if normalized_level in (1, 2, 3):
        # Bump any existing occupant of this slot to None
        existing = db.query(FeedItem).filter(
            FeedItem.featured_level == normalized_level,
            FeedItem.artifact_id != artifact_id,
        ).first()
        if existing:
            existing.featured_level = None
            db.add(existing)

    feed_item.featured_level = normalized_level
    db.commit()
    db.refresh(feed_item)
    return feed_item
