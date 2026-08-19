"""
Folder-scoped permission resolution and enforcement.

Scope owners:
- Admin user → unrestricted
- Global API key (no user_id) → unrestricted
- Editor/member user → union of user_folder_scopes grants
- API key with user_id → same grants as that user (permission source only;
  identity stays agent)

Zero grants → no content access.
Cross-folder embeds: read (and remove-from-parent) allowed when the item is
referenced by an in-scope artifact; search/list/delete of the item itself stay
strictly scoped.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Set
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.api_key import APIKey
from models.artifact import Artifact
from models.asset import Asset
from models.enums import RoleEnum
from models.folder import Folder
from models.user import User
from models.user_folder_scope import UserFolderScope


@dataclass
class AuthContext:
    """Authenticated principal. Exactly one of user / api_key is set."""
    user: Optional[User] = None
    api_key: Optional[APIKey] = None

    @property
    def is_agent(self) -> bool:
        return self.api_key is not None

    @property
    def actor(self) -> dict:
        if self.user is not None:
            return {
                "type": "user",
                "id": str(self.user.id),
                "name": self.user.email,
            }
        return {"type": "agent", "id": None, "name": None}


@dataclass
class Scope:
    """Resolved folder access for a principal."""
    unrestricted: bool
    grant_folder_ids: Optional[Set[UUID]] = None  # None when unrestricted

    @property
    def is_unrestricted(self) -> bool:
        return self.unrestricted

    @property
    def has_any_access(self) -> bool:
        if self.unrestricted:
            return True
        return bool(self.grant_folder_ids)


def resolve_scope(db: Session, ctx: AuthContext) -> Scope:
    """Resolve folder scope from an AuthContext."""
    if ctx.user is not None:
        if ctx.user.role == RoleEnum.admin:
            return Scope(unrestricted=True, grant_folder_ids=None)
        return _scope_for_user_id(db, ctx.user.id)

    if ctx.api_key is not None:
        if ctx.api_key.user_id is None:
            return Scope(unrestricted=True, grant_folder_ids=None)
        return _scope_for_user_id(db, ctx.api_key.user_id)

    return Scope(unrestricted=False, grant_folder_ids=set())


def _scope_for_user_id(db: Session, user_id: int) -> Scope:
    rows = (
        db.query(UserFolderScope.folder_id)
        .filter(UserFolderScope.user_id == user_id)
        .all()
    )
    return Scope(
        unrestricted=False,
        grant_folder_ids={row.folder_id for row in rows},
    )


def get_scope_folder_ids(db: Session, scope: Scope) -> Optional[Set[UUID]]:
    """
    Return the set of all folder IDs in scope (grants + descendants).

    Returns None when unrestricted (meaning "all folders").
    Returns empty set when the principal has zero grants.
    """
    if scope.is_unrestricted:
        return None
    grant_ids = scope.grant_folder_ids or set()
    if not grant_ids:
        return set()

    scope_ids: Set[UUID] = set(grant_ids)
    queue = list(grant_ids)
    while queue:
        children = (
            db.query(Folder.id)
            .filter(Folder.parent_id.in_(queue))
            .all()
        )
        queue = []
        for (cid,) in children:
            if cid not in scope_ids:
                scope_ids.add(cid)
                queue.append(cid)
    return scope_ids


def folder_in_scope(db: Session, scope: Scope, folder: Optional[Folder]) -> bool:
    """True if folder is a grant root or a descendant of a grant."""
    if scope.is_unrestricted:
        return True
    if folder is None:
        return False
    grant_ids = scope.grant_folder_ids or set()
    if not grant_ids:
        return False

    current = folder
    seen: Set[UUID] = set()
    while current is not None:
        if current.id in seen:
            break
        seen.add(current.id)
        if current.id in grant_ids:
            return True
        if current.parent_id:
            current = db.query(Folder).filter(Folder.id == current.parent_id).first()
        else:
            current = None
    return False


def folder_id_in_scope(db: Session, scope: Scope, folder_id: Optional[UUID]) -> bool:
    if scope.is_unrestricted:
        return True
    if folder_id is None:
        # Null folder_id means root / My Drive for loose assets
        return False
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    return folder_in_scope(db, scope, folder)


def assert_folder_in_scope(
    db: Session,
    scope: Scope,
    folder: Optional[Folder],
    detail: str = "Access denied",
) -> None:
    if not folder_in_scope(db, scope, folder):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def assert_folder_id_in_scope(
    db: Session,
    scope: Scope,
    folder_id: Optional[UUID],
    detail: str = "Access denied",
) -> None:
    if not folder_id_in_scope(db, scope, folder_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def asset_in_scope(db: Session, scope: Scope, asset: Asset) -> bool:
    """Strict scope: asset lives in an in-scope folder."""
    if scope.is_unrestricted:
        return True
    return folder_id_in_scope(db, scope, asset.folder_id)


def artifact_in_scope(db: Session, scope: Scope, artifact: Artifact) -> bool:
    """Strict scope: artifact lives in an in-scope folder."""
    if scope.is_unrestricted:
        return True
    return folder_id_in_scope(db, scope, artifact.folder_id)


def _referenced_by_in_scope(db: Session, scope: Scope, item_id: UUID) -> bool:
    """
    True if any in-scope artifact's content or meta JSON contains the item id.

    Covers composer sections, gallery items, note/map linked assets, cover
    images (meta.cover_asset_id), etc.
    """
    folder_ids = get_scope_folder_ids(db, scope)
    if folder_ids is None:
        return True
    if not folder_ids:
        return False

    needle = str(item_id)
    artifacts = (
        db.query(Artifact)
        .filter(Artifact.folder_id.in_(folder_ids))
        .all()
    )
    for artifact in artifacts:
        content = artifact.content or {}
        meta = artifact.meta or {}
        try:
            if needle in json.dumps(content, default=str):
                return True
            if needle in json.dumps(meta, default=str):
                return True
        except (TypeError, ValueError):
            continue
    return False


def can_read_asset(db: Session, scope: Scope, asset: Asset) -> bool:
    """Read allowed if in-scope or referenced by an in-scope artifact."""
    if asset_in_scope(db, scope, asset):
        return True
    return _referenced_by_in_scope(db, scope, asset.id)


def can_read_artifact(db: Session, scope: Scope, artifact: Artifact) -> bool:
    """Read allowed if in-scope or referenced by an in-scope parent artifact."""
    if artifact_in_scope(db, scope, artifact):
        return True
    return _referenced_by_in_scope(db, scope, artifact.id)


def assert_can_read_asset(
    db: Session,
    scope: Scope,
    asset: Asset,
    detail: str = "Access denied",
) -> None:
    if not can_read_asset(db, scope, asset):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def assert_can_read_artifact(
    db: Session,
    scope: Scope,
    artifact: Artifact,
    detail: str = "Access denied",
) -> None:
    if not can_read_artifact(db, scope, artifact):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def assert_asset_in_scope(
    db: Session,
    scope: Scope,
    asset: Asset,
    detail: str = "Access denied",
) -> None:
    """Strict write/delete check (no embed exception)."""
    if not asset_in_scope(db, scope, asset):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def assert_artifact_in_scope(
    db: Session,
    scope: Scope,
    artifact: Artifact,
    detail: str = "Access denied",
) -> None:
    """Strict write/delete check (no embed exception)."""
    if not artifact_in_scope(db, scope, artifact):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def filter_folders_in_scope(db: Session, scope: Scope, folders: list) -> list:
    """Filter a list of Folder objects to those in scope."""
    if scope.is_unrestricted:
        return folders
    return [f for f in folders if folder_in_scope(db, scope, f)]
