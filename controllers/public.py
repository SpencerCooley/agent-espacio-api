"""
Public view controller.

Handles resolving public magic IDs and checking derived access.
"""
from typing import Optional, Union, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from models.folder import Folder
from models.asset import Asset
from models.artifact import Artifact


def resolve_public_item(db: Session, magic_id: UUID) -> Tuple[Optional[Union[Folder, Asset, Artifact]], str]:
    """
    Resolve a public magic_id to an item.
    
    Checks folders, assets, and artifacts in that order.
    
    Args:
        db: Database session
        magic_id: Public magic ID
        
    Returns:
        Tuple of (item, kind) where kind is 'folder', 'asset', or 'artifact'.
        Returns (None, '') if not found.
    """
    # Check folders by public_magic_id
    folder = db.query(Folder).filter(Folder.public_magic_id == magic_id).first()
    if folder and is_folder_public(db, folder):
        return folder, 'folder'
    
    # Check assets by public_magic_id
    asset = db.query(Asset).filter(Asset.public_magic_id == magic_id).first()
    if asset and is_asset_public(db, asset):
        return asset, 'asset'
    
    # Check artifacts by public_magic_id
    artifact = db.query(Artifact).filter(Artifact.public_magic_id == magic_id).first()
    if artifact and is_artifact_public(db, artifact):
        return artifact, 'artifact'
    
    # Fallback: check by direct ID for inherited public access
    # (items inside a public folder don't have their own magic_id)
    try:
        id_uuid = magic_id
        
        # Check folder by ID
        folder = db.query(Folder).filter(Folder.id == id_uuid).first()
        if folder and is_folder_public(db, folder):
            return folder, 'folder'
        
        # Check asset by ID
        asset = db.query(Asset).filter(Asset.id == id_uuid).first()
        if asset and is_asset_public(db, asset):
            return asset, 'asset'
        
        # Check artifact by ID
        artifact = db.query(Artifact).filter(Artifact.id == id_uuid).first()
        if artifact and is_artifact_public(db, artifact):
            return artifact, 'artifact'
    except:
        pass
    
    return None, ''


def is_folder_public(db: Session, folder: Folder) -> bool:
    """
    Check if a folder is publicly accessible.
    
    A folder is public if:
    1. It is directly marked as public, OR
    2. Any ancestor folder is public (inherited)
    
    Args:
        db: Database session
        folder: Folder to check
        
    Returns:
        True if public, False otherwise
    """
    if folder.is_public:
        return True
    
    # Check if any ancestor is public
    current = folder
    while current.parent_id:
        parent = db.query(Folder).filter(Folder.id == current.parent_id).first()
        if not parent:
            break
        if parent.is_public:
            return True
        current = parent
    
    return False





def is_asset_public(db: Session, asset: Asset) -> bool:
    """
    Check if an asset is publicly accessible.

    An asset is public if:
    1. It is directly marked as public, OR
    2. Its parent folder or any ancestor is public, OR
    3. It is referenced by any publicly accessible artifact (derived access).
       This includes nested access: a public composer references Note B, and
       Note B contains image Asset C — Asset C is public. Also covers
       meta.cover_asset_id, linked_asset_ids, image nodes, and gallery items.
    4. It is used as public branding (logo / background) in settings.

    Args:
        db: Database session
        asset: Asset to check

    Returns:
        True if public, False otherwise
    """
    # Direct public
    if asset.is_public:
        return True

    # Parent folder or any ancestor is public
    if asset.folder_id:
        folder = db.query(Folder).filter(Folder.id == asset.folder_id).first()
        if folder and is_folder_public(db, folder):
            return True

    # Derived access: referenced by any publicly accessible artifact
    if _is_asset_referenced_by_public_artifact(db, asset.id):
        return True

    # Derived access: used as public branding (logo / background) in settings
    if _is_asset_public_branding(db, asset.id):
        return True

    return False


def _is_asset_public_branding(db: Session, asset_id: UUID) -> bool:
    """Check if an asset is used as branding (logo/background) for the public site."""
    from models.settings import Setting
    row = db.query(Setting).filter(Setting.key == "branding").first()
    if not row or not isinstance(row.value, dict):
        return False
    asset_id_str = str(asset_id)
    for key in ("logo_light_asset_id", "logo_dark_asset_id", "background_asset_id"):
        if str(row.value.get(key) or "") == asset_id_str:
            return True
    return False


def _is_asset_referenced_by_public_artifact(db: Session, asset_id: UUID) -> bool:
    """
    Check if an asset is referenced by any publicly accessible artifact.

    This handles both direct and nested derived access:
    - A public artifact embeds Asset A (image node, gallery item, cover image).
    - A public composer references Note B, and Note B embeds Asset C —
      Asset C is public too.

    Scans only artifacts known to be public (directly, via folder, or via
    composer reference) to avoid a full table scan.
    """
    asset_id_str = str(asset_id)

    # Collect all artifacts that are publicly accessible
    public_artifacts: list[Artifact] = []
    seen_ids: set[str] = set()

    def _add(artifact: Artifact | None):
        if artifact and str(artifact.id) not in seen_ids:
            seen_ids.add(str(artifact.id))
            public_artifacts.append(artifact)

    # 1. Directly public artifacts
    for art in db.query(Artifact).filter(Artifact.is_public == True).all():
        _add(art)

    # 2. Artifacts in public folders
    public_folder_ids = [f.id for f in db.query(Folder).filter(Folder.is_public == True).all()]
    if public_folder_ids:
        for art in db.query(Artifact).filter(Artifact.folder_id.in_(public_folder_ids)).all():
            _add(art)

    # 3. Artifacts referenced by public composers (nested derived access)
    referenced_ids: set[str] = set()
    public_composers = db.query(Artifact).filter(
        Artifact.is_public == True,
        Artifact.type == "composer"
    ).all()
    for composer in public_composers:
        sections = (composer.content or {}).get("sections", [])
        for section in sections:
            if isinstance(section, dict):
                aid = section.get("artifact_id")
                if aid:
                    referenced_ids.add(str(aid))

    if public_folder_ids:
        folder_composers = db.query(Artifact).filter(
            Artifact.folder_id.in_(public_folder_ids),
            Artifact.type == "composer"
        ).all()
        for composer in folder_composers:
            sections = (composer.content or {}).get("sections", [])
            for section in sections:
                if isinstance(section, dict):
                    aid = section.get("artifact_id")
                    if aid:
                        referenced_ids.add(str(aid))

    if referenced_ids:
        for art in db.query(Artifact).filter(Artifact.id.in_(list(referenced_ids))).all():
            _add(art)

    # Scan all collected public artifacts for the asset (covers meta.cover_asset_id too)
    for artifact in public_artifacts:
        if _artifact_references_asset(artifact, asset_id_str):
            return True

    return False


def is_artifact_public(db: Session, artifact: Artifact) -> bool:
    """
    Check if an artifact is publicly accessible.
    
    An artifact is public if:
    1. It is directly marked as public, OR
    2. Its parent folder or any ancestor is public, OR
    3. It is referenced by a public composition (derived access)
    
    Args:
        db: Database session
        artifact: Artifact to check
        
    Returns:
        True if public, False otherwise
    """
    # Direct public
    if artifact.is_public:
        return True
    
    # Parent folder or any ancestor is public
    if artifact.folder_id:
        folder = db.query(Folder).filter(Folder.id == artifact.folder_id).first()
        if folder and is_folder_public(db, folder):
            return True
    
    # Derived access: referenced by a public composition
    if is_artifact_referenced_by_public_composer(db, artifact.id):
        return True
    
    return False


def is_artifact_referenced_by_public_composer(db: Session, artifact_id: UUID) -> bool:
    """
    Check if an artifact is referenced by any public composition.
    
    Looks through all public composer artifacts' content for sections
    with artifact_id matching the given artifact_id.
    
    Args:
        db: Database session
        artifact_id: Artifact UUID to check
        
    Returns:
        True if referenced by a public composer, False otherwise
    """
    artifact_id_str = str(artifact_id)
    
    # Query all public composers
    public_composers = db.query(Artifact).filter(
        Artifact.is_public == True,
        Artifact.type == "composer"
    ).all()
    
    for composer in public_composers:
        content = composer.content
        if content and isinstance(content, dict):
            sections = content.get("sections", [])
            if isinstance(sections, list):
                for section in sections:
                    if isinstance(section, dict) and section.get("artifact_id") == artifact_id_str:
                        return True
    
    # Also check composers in public folders
    public_folders = db.query(Folder).filter(Folder.is_public == True).all()
    public_folder_ids = [f.id for f in public_folders]
    
    if public_folder_ids:
        folder_composers = db.query(Artifact).filter(
            Artifact.folder_id.in_(public_folder_ids),
            Artifact.type == "composer"
        ).all()
        
        for composer in folder_composers:
            content = composer.content
            if content and isinstance(content, dict):
                sections = content.get("sections", [])
                if isinstance(sections, list):
                    for section in sections:
                        if isinstance(section, dict) and section.get("artifact_id") == artifact_id_str:
                            return True
    
    return False


def _artifact_references_asset(artifact: Artifact, asset_id_str: str) -> bool:
    """
    Return True if an artifact references the given asset anywhere:
    - meta.cover_asset_id (featured / cover image)
    - content.linked_asset_ids
    - TipTap image nodes (data-asset-id)
    - gallery items (asset_id or association.id)
    """
    # Featured image lives in meta.cover_asset_id, not content
    meta = artifact.meta or {}
    if str(meta.get("cover_asset_id") or "") == asset_id_str:
        return True

    content = artifact.content
    if not content or not isinstance(content, dict):
        return False

    linked_ids = content.get("linked_asset_ids", [])
    if asset_id_str in linked_ids:
        return True

    doc_content = content.get("content", {})
    if isinstance(doc_content, dict):
        nodes = doc_content.get("content", [])
        if _scan_nodes_for_asset_id(nodes, asset_id_str):
            return True
    elif isinstance(doc_content, list):
        if _scan_nodes_for_asset_id(doc_content, asset_id_str):
            return True

    gallery_items = content.get("items", [])
    if _scan_gallery_items_for_asset_id(gallery_items, asset_id_str):
        return True

    return False


def _scan_nodes_for_asset_id(nodes, asset_id_str):
    """
    Recursively scan TipTap content nodes for image nodes with data-asset-id.
    
    Args:
        nodes: List of TipTap nodes
        asset_id_str: Asset ID string to look for
        
    Returns:
        True if found, False otherwise
    """
    if not isinstance(nodes, list):
        return False
    
    for node in nodes:
        if not isinstance(node, dict):
            continue
        
        if node.get('type') == 'image':
            attrs = node.get('attrs', {})
            if attrs.get('data-asset-id') == asset_id_str:
                return True
        
        # Recurse into child content
        children = node.get('content', [])
        if children and _scan_nodes_for_asset_id(children, asset_id_str):
            return True
    
    return False


def _scan_gallery_items_for_asset_id(items, asset_id_str):
    """
    Scan gallery items for an asset_id match.

    Args:
        items: List of gallery item dicts with 'asset_id' keys
        asset_id_str: Asset ID string to look for

    Returns:
        True if found, False otherwise
    """
    if not isinstance(items, list):
        return False

    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get('asset_id') == asset_id_str:
            return True
        # Composer gallery format: {association: {id: ..., type: 'asset'}}
        assoc = item.get('association')
        if isinstance(assoc, dict) and assoc.get('type') == 'asset' and str(assoc.get('id', '')) == asset_id_str:
            return True

    return False


def get_public_folder_contents(db: Session, folder: Folder) -> Tuple[list, list, list]:
    """
    Get all contents of a public folder.

    Returns subfolders, assets, and artifacts that are in this folder.

    Args:
        db: Database session
        folder: Public folder

    Returns:
        Tuple of (subfolders, assets, artifacts)
    """
    # Get subfolders (all subfolders are visible because parent is public)
    subfolders = db.query(Folder).filter(
        Folder.parent_id == folder.id
    ).order_by(Folder.name).all()

    # Get all assets (public by folder inheritance)
    assets = db.query(Asset).filter(
        Asset.folder_id == folder.id
    ).order_by(Asset.name).all()

    # Get all artifacts (public by folder inheritance)
    artifacts = db.query(Artifact).filter(
        Artifact.folder_id == folder.id
    ).order_by(Artifact.name).all()

    return subfolders, assets, artifacts


def search_public_folder_scope(
    db: Session,
    folder: Folder,
    query: str,
    limit: int = 50
) -> Tuple[list, list, list]:
    """
    Search for publicly accessible items by name within a public folder
    and all its descendants.

    Only returns items that are publicly accessible (directly public,
    or in a public folder/ancestor, or have derived access).

    Args:
        db: Database session
        folder: The public folder to search within
        query: Search term (case-insensitive partial match)
        limit: Maximum results per kind

    Returns:
        Tuple of (matching_folders, matching_assets, matching_artifacts)
    """
    search_pattern = f"%{query}%"

    # Find all descendant folder IDs recursively (including self)
    # We walk the actual parent_id tree instead of relying on the path column,
    # which guarantees we find every descendant at any nesting depth.
    descendant_ids: list[UUID] = []
    queue = [folder.id]
    while queue:
        children = db.query(Folder).filter(Folder.parent_id.in_(queue)).all()
        queue = [c.id for c in children if c.id not in descendant_ids]
        descendant_ids.extend(queue)

    # Always include the target folder itself
    if folder.id not in descendant_ids:
        descendant_ids.append(folder.id)

    if not descendant_ids:
        return [], [], []

    # Search folders within scope that are publicly accessible
    folder_results = db.query(Folder).filter(
        Folder.id.in_(descendant_ids),
        Folder.is_root == False,
        Folder.name.ilike(search_pattern)
    ).order_by(Folder.name).limit(limit).all()
    folder_results = [f for f in folder_results if is_folder_public(db, f)]

    # Search assets within scope that are publicly accessible
    asset_results = db.query(Asset).filter(
        Asset.folder_id.in_(descendant_ids),
        Asset.name.ilike(search_pattern)
    ).order_by(Asset.name).limit(limit).all()
    asset_results = [a for a in asset_results if is_asset_public(db, a)]

    # Search artifacts within scope that are publicly accessible
    artifact_results = db.query(Artifact).filter(
        Artifact.folder_id.in_(descendant_ids),
        Artifact.name.ilike(search_pattern)
    ).order_by(Artifact.name).limit(limit).all()
    artifact_results = [ar for ar in artifact_results if is_artifact_public(db, ar)]

    return folder_results, asset_results, artifact_results


def list_public_sitemap(db: Session) -> list:
    """
    List all publicly accessible items that have their own public_magic_id.

    These are the canonical shareable URLs used for the client's sitemap.xml
    and llms.txt. Items that are public only through inheritance (a public
    ancestor folder) are reachable via their parent's public URL and are not
    listed separately.

    Args:
        db: Database session

    Returns:
        List of dicts: {kind, id, type, public_magic_id, updated_at}
    """
    folders = db.query(Folder).filter(Folder.public_magic_id.isnot(None)).all()
    assets = db.query(Asset).filter(Asset.public_magic_id.isnot(None)).all()
    artifacts = db.query(Artifact).filter(Artifact.public_magic_id.isnot(None)).all()

    items = []

    for f in folders:
        if is_folder_public(db, f):
            items.append({
                "kind": "folder",
                "id": str(f.id),
                "name": f.name,
                "type": None,
                "public_magic_id": str(f.public_magic_id),
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            })

    for a in assets:
        if is_asset_public(db, a):
            items.append({
                "kind": "asset",
                "id": str(a.id),
                "name": a.name,
                "type": None,
                "public_magic_id": str(a.public_magic_id),
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            })

    for ar in artifacts:
        if is_artifact_public(db, ar):
            items.append({
                "kind": "artifact",
                "id": str(ar.id),
                "name": ar.name,
                "type": ar.type,
                "public_magic_id": str(ar.public_magic_id),
                "updated_at": ar.updated_at.isoformat() if ar.updated_at else None,
            })

    return items
