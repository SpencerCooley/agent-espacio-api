"""
Signed URL controller for secure asset downloads.

Generates time-bound HMAC-signed URLs that allow unauthenticated
access to private assets for a short duration.
"""
import hmac
import hashlib
import base64
import time
from typing import Optional
from uuid import UUID

from config.settings import get_settings


SETTINGS = get_settings()
SECRET_KEY = SETTINGS.secret_key.encode()
DEFAULT_EXPIRY_SECONDS = 600  # 10 minutes


def _encode_token(asset_id: str, expiry: int, size: Optional[int]) -> str:
    """Encode token components into a compact string."""
    size_str = str(size) if size is not None else ""
    raw = f"{asset_id}:{expiry}:{size_str}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_token(token: str) -> tuple[str, int, Optional[int]]:
    """Decode a token string back into components."""
    padding = 4 - len(token) % 4
    if padding != 4:
        token += "=" * padding
    raw = base64.urlsafe_b64decode(token.encode()).decode()
    parts = raw.split(":")
    asset_id = parts[0]
    expiry = int(parts[1])
    size = int(parts[2]) if parts[2] else None
    return asset_id, expiry, size


def _sign(asset_id: str, expiry: int, size: Optional[int]) -> str:
    """Generate HMAC-SHA256 signature for the given parameters."""
    size_str = str(size) if size is not None else ""
    message = f"{asset_id}:{expiry}:{size_str}"
    return hmac.new(SECRET_KEY, message.encode(), hashlib.sha256).hexdigest()


def generate_signed_url(asset_id: UUID, size: Optional[int] = None, expiry_seconds: int = DEFAULT_EXPIRY_SECONDS) -> str:
    """
    Generate a signed download URL for an asset.
    
    Args:
        asset_id: Asset UUID
        size: Optional thumbnail size
        expiry_seconds: How long the URL should be valid (default 600 = 10 min)
        
    Returns:
        Complete signed URL path (e.g., /assets/{id}/download?signed=...&exp=...)
    """
    expiry = int(time.time()) + expiry_seconds
    asset_id_str = str(asset_id)
    signature = _sign(asset_id_str, expiry, size)
    
    # Build the signed parameter: base64(asset_id:expiry:size:signature)
    size_str = str(size) if size is not None else ""
    signed_payload = f"{asset_id_str}:{expiry}:{size_str}:{signature}"
    signed = base64.urlsafe_b64encode(signed_payload.encode()).decode().rstrip("=")
    
    url = f"/assets/{asset_id_str}/download"
    params = f"?signed={signed}"
    if size is not None:
        params += f"&size={size}"
    return url + params


def verify_signed_url(signed_param: str, asset_id: UUID, size: Optional[int] = None) -> bool:
    """
    Verify a signed URL parameter.
    
    Args:
        signed_param: The value of the ?signed= query parameter
        asset_id: Expected asset ID
        size: Expected thumbnail size
        
    Returns:
        True if the signature is valid and not expired
    """
    try:
        # Add padding back for base64 decoding
        padding = 4 - len(signed_param) % 4
        if padding != 4:
            signed_param += "=" * padding
        
        decoded = base64.urlsafe_b64decode(signed_param.encode()).decode()
        parts = decoded.split(":")
        if len(parts) != 4:
            return False
        
        token_asset_id, token_expiry_str, token_size_str, token_signature = parts
        
        # Validate asset ID match
        if token_asset_id != str(asset_id):
            return False
        
        # Validate expiry
        token_expiry = int(token_expiry_str)
        if token_expiry < time.time():
            return False
        
        # Validate size match
        expected_size = str(size) if size is not None else ""
        if token_size_str != expected_size:
            return False
        
        # Validate signature
        expected_signature = _sign(token_asset_id, token_expiry, size)
        return hmac.compare_digest(token_signature, expected_signature)
    except Exception:
        return False


def _scan_content_for_assets(content: dict, asset_ids: set) -> None:
    """Recursively scan content dict for asset_id references."""
    if not isinstance(content, dict):
        return
    
    # Gallery items
    items = content.get('items', [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                if item.get('asset_id'):
                    asset_ids.add(str(item['asset_id']))
                # Composer gallery format
                assoc = item.get('association')
                if isinstance(assoc, dict) and assoc.get('id') and assoc.get('type') == 'asset':
                    asset_ids.add(str(assoc['id']))
    
    # Note/image nodes — TipTap doc format: {"type": "doc", "content": [...]}
    doc_content = content.get('content', {})
    if isinstance(doc_content, list):
        # Top-level content is the TipTap node array
        _scan_nodes_for_assets(doc_content, asset_ids)
    elif isinstance(doc_content, dict):
        # Nested doc structure (e.g. composer sections)
        nodes = doc_content.get('content', [])
        _scan_nodes_for_assets(nodes, asset_ids)

    # Composer sections
    sections = content.get('sections', [])
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict):
                if section.get('artifact_id'):
                    asset_ids.add(str(section['artifact_id']))
                # Some sections have inline content with images
                section_content = section.get('content')
                if isinstance(section_content, dict):
                    _scan_content_for_assets(section_content, asset_ids)


def _scan_nodes_for_assets(nodes: list, asset_ids: set) -> None:
    """Recursively scan TipTap content nodes for asset references."""
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        attrs = node.get('attrs', {})
        if attrs.get('data-asset-id'):
            asset_ids.add(str(attrs['data-asset-id']))
        # Also check src for /assets/{id}/download pattern
        src = attrs.get('src', '')
        if '/assets/' in src and '/download' in src:
            parts = src.split('/')
            for i, part in enumerate(parts):
                if part == 'assets' and i + 1 < len(parts):
                    asset_ids.add(parts[i + 1])
        # Recurse into child nodes
        children = node.get('content', [])
        _scan_nodes_for_assets(children, asset_ids)


def enrich_content_with_signed_urls(content: dict, expiry_seconds: int = 3600) -> dict:
    """
    Add signed URLs to all asset references within artifact content.
    
    Mutates content in-place to add 'signed_url' fields next to asset references.
    Returns the enriched content dict.
    """
    if not isinstance(content, dict):
        return content
    
    # Collect all unique asset IDs
    asset_ids = set()
    _scan_content_for_assets(content, asset_ids)
    
    if not asset_ids:
        return content
    
    # Generate signed URLs for all found assets
    signed_urls = {}
    for asset_id in asset_ids:
        try:
            signed_urls[asset_id] = generate_signed_url(asset_id, size=512, expiry_seconds=expiry_seconds)
        except Exception:
            pass
    
    if not signed_urls:
        return content
    
    # Inject signed URLs back into content
    _inject_signed_urls(content, signed_urls)
    
    return content


def _inject_signed_urls(content: dict, signed_urls: dict) -> None:
    """Inject signed_url fields into content dict where asset_id references exist."""
    if not isinstance(content, dict):
        return
    
    # Gallery items
    items = content.get('items', [])
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                asset_id = item.get('asset_id')
                if asset_id and str(asset_id) in signed_urls:
                    item['signed_url'] = signed_urls[str(asset_id)]
                # Composer gallery format
                assoc = item.get('association')
                if isinstance(assoc, dict) and assoc.get('type') == 'asset':
                    assoc_id = str(assoc.get('id', ''))
                    if assoc_id and assoc_id in signed_urls:
                        item['signed_url'] = signed_urls[assoc_id]
    
    # Note/image nodes — TipTap doc format: {"type": "doc", "content": [...]}
    doc_content = content.get('content', {})
    if isinstance(doc_content, list):
        # Top-level content is the TipTap node array
        _inject_signed_urls_into_nodes(doc_content, signed_urls)
    elif isinstance(doc_content, dict):
        # Nested doc structure (e.g. composer sections)
        nodes = doc_content.get('content', [])
        _inject_signed_urls_into_nodes(nodes, signed_urls)

    # Composer sections
    sections = content.get('sections', [])
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict):
                section_content = section.get('content')
                if isinstance(section_content, dict):
                    _inject_signed_urls(section_content, signed_urls)


def _inject_signed_urls_into_nodes(nodes: list, signed_urls: dict) -> None:
    """Inject signed URLs into TipTap content nodes."""
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        attrs = node.get('attrs', {})
        asset_id = attrs.get('data-asset-id')
        # Fallback: extract asset ID from src if data-asset-id is missing
        if not asset_id:
            src = attrs.get('src', '')
            if '/assets/' in src and '/download' in src:
                parts = src.split('/')
                for i, part in enumerate(parts):
                    if part == 'assets' and i + 1 < len(parts):
                        asset_id = parts[i + 1]
                        break
        if asset_id and str(asset_id) in signed_urls:
            attrs['src'] = signed_urls[str(asset_id)]
            attrs['signed_url'] = signed_urls[str(asset_id)]
        # Recurse into child nodes
        children = node.get('content', [])
        _inject_signed_urls_into_nodes(children, signed_urls)
