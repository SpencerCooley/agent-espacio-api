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


def _is_folder_or_ancestor_public(db: Session, folder: Folder) -> bool:
    """Check if a folder or any of its ancestors are public."""
    if folder.is_public:
        return True
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
    3. It is linked from a public artifact (derived access)
    
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
        if folder and _is_folder_or_ancestor_public(db, folder):
            return True
    
    # Derived access: linked from a public artifact
    if is_asset_linked_by_public_artifact(db, asset.id):
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
        if folder and _is_folder_or_ancestor_public(db, folder):
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


def is_asset_linked_by_public_artifact(db: Session, asset_id: UUID) -> bool:
    """
    Check if an asset is linked by any public artifact.
    
    Looks through artifact.content for image nodes with data-asset-id
    matching the given asset_id.
    
    Args:
        db: Database session
        asset_id: Asset UUID to check
        
    Returns:
        True if linked by a public artifact, False otherwise
    """
    asset_id_str = str(asset_id)
    
    # Query all public artifacts
    public_artifacts = db.query(Artifact).filter(Artifact.is_public == True).all()
    
    for artifact in public_artifacts:
        # Check linked_asset_ids at top level
        content = artifact.content
        if content and isinstance(content, dict):
            linked_ids = content.get('linked_asset_ids', [])
            if asset_id_str in linked_ids:
                return True

            # Also check for data-asset-id in content nodes
            doc_content = content.get('content', {})
            if isinstance(doc_content, dict):
                nodes = doc_content.get('content', [])
                if _scan_nodes_for_asset_id(nodes, asset_id_str):
                    return True

            # Also check gallery items
            gallery_items = content.get('items', [])
            if _scan_gallery_items_for_asset_id(gallery_items, asset_id_str):
                return True

            # Also check composer sections
            sections = content.get('sections', [])
            if _scan_composer_sections_for_asset_id(sections, asset_id_str):
                return True

    # Also check artifacts in public folders
    # First get all public folders
    public_folders = db.query(Folder).filter(Folder.is_public == True).all()
    public_folder_ids = [f.id for f in public_folders]

    if public_folder_ids:
        folder_artifacts = db.query(Artifact).filter(
            Artifact.folder_id.in_(public_folder_ids)
        ).all()

        for artifact in folder_artifacts:
            content = artifact.content
            if content and isinstance(content, dict):
                linked_ids = content.get('linked_asset_ids', [])
                if asset_id_str in linked_ids:
                    return True

                doc_content = content.get('content', {})
                if isinstance(doc_content, dict):
                    nodes = doc_content.get('content', [])
                    if _scan_nodes_for_asset_id(nodes, asset_id_str):
                        return True

                # Also check gallery items
                gallery_items = content.get('items', [])
                if _scan_gallery_items_for_asset_id(gallery_items, asset_id_str):
                    return True

                # Also check composer sections
                sections = content.get('sections', [])
                if _scan_composer_sections_for_asset_id(sections, asset_id_str):
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
        if isinstance(item, dict) and item.get('asset_id') == asset_id_str:
            return True

    return False


def _scan_composer_sections_for_asset_id(sections, asset_id_str):
    """
    Scan composer sections for an artifact_id matching an asset.

    Args:
        sections: List of composer section dicts with 'artifact_id' keys
        asset_id_str: Asset ID string to look for

    Returns:
        True if found, False otherwise
    """
    if not isinstance(sections, list):
        return False

    for section in sections:
        if isinstance(section, dict) and section.get('artifact_id') == asset_id_str:
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
    folder_results = [f for f in folder_results if _is_folder_or_ancestor_public(db, f)]

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
