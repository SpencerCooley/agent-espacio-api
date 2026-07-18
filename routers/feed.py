"""
Feed router.

Public and authenticated endpoints for the curated public feed.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db, require_auth
from controllers.feed import list_feed_items, add_to_feed, remove_from_feed, reorder_feed_item, set_featured_level
from controllers.public import is_artifact_public
from models.feed_item import FeedItem

router = APIRouter(
    prefix="/feed",
    tags=["Feed"],
)


@router.get("")
async def get_feed(
    tag: Optional[str] = Query(None, description="Filter by metadata tag"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get the curated public feed.

    Returns composer artifacts that have been explicitly added to the feed
    and are publicly accessible.

    Query params:
    - tag: Filter by a tag stored in artifact.meta.tags
    - limit: Number of items (default 20, max 100)
    - offset: Pagination offset
    """
    result = list_feed_items(db, tag=tag, limit=limit, offset=offset)
    return result


@router.get("/items/{artifact_id}")
async def get_feed_item_status(
    artifact_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """
    Check if an artifact is in the curated feed.

    Returns the feed item if found, 404 otherwise.
    """
    feed_item = db.query(FeedItem).filter(FeedItem.artifact_id == artifact_id).first()
    if not feed_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact is not in the feed"
        )
    return {
        "id": str(feed_item.id),
        "artifact_id": str(feed_item.artifact_id),
        "sort_order": feed_item.sort_order,
        "featured_level": feed_item.featured_level,
        "created_at": feed_item.created_at.isoformat() if feed_item.created_at else None,
        "updated_at": feed_item.updated_at.isoformat() if feed_item.updated_at else None,
    }


@router.post("/items")
async def create_feed_item(
    artifact_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """
    Add an artifact to the curated public feed.

    Requires authentication. The artifact does not need to be public
    at the time of adding — it simply won't appear in the public feed
    until it becomes public.
    """
    feed_item = add_to_feed(db, artifact_id)
    return {
        "id": str(feed_item.id),
        "artifact_id": str(feed_item.artifact_id),
        "sort_order": feed_item.sort_order,
        "featured_level": feed_item.featured_level,
        "created_at": feed_item.created_at.isoformat() if feed_item.created_at else None,
    }


@router.delete("/items/{artifact_id}")
async def delete_feed_item(
    artifact_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """
    Remove an artifact from the curated public feed.

    Requires authentication.
    """
    removed = remove_from_feed(db, artifact_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed item not found"
        )
    return {"removed": True}


@router.put("/items/{artifact_id}/order")
async def update_feed_item_order(
    artifact_id: UUID,
    sort_order: int = Query(..., description="New sort order integer"),
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """
    Update the sort order of a feed item.

    Requires authentication.
    """
    feed_item = reorder_feed_item(db, artifact_id, sort_order)
    if not feed_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed item not found"
        )
    return {
        "id": str(feed_item.id),
        "artifact_id": str(feed_item.artifact_id),
        "sort_order": feed_item.sort_order,
    }


@router.put("/items/{artifact_id}/featured")
async def update_feed_item_featured_level(
    artifact_id: UUID,
    featured_level: Optional[int] = Query(None, ge=0, le=3, description="Featured level: 1, 2, 3 to feature, or 0/None to clear"),
    db: Session = Depends(get_db),
    user=Depends(require_auth),
):
    """
    Set or clear the featured level of a feed item.

    Levels 1, 2, and 3 are exclusive featured slots. Setting a new item to an
    occupied slot bumps the previous occupant to not featured (X). Passing 0
    or None clears the featured level.

    Requires authentication.
    """
    feed_item = set_featured_level(db, artifact_id, featured_level)
    if not feed_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed item not found"
        )
    return {
        "id": str(feed_item.id),
        "artifact_id": str(feed_item.artifact_id),
        "sort_order": feed_item.sort_order,
        "featured_level": feed_item.featured_level,
    }
