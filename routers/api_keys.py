"""
API Keys router.

Endpoints for API key management:
- GET /api-keys - List all API keys (admin only)
- GET /api-keys/me - List the current user's assigned keys with full values
- POST /api-keys - Create new API key (admin only)
- DELETE /api-keys/{key_id} - Revoke API key (admin only)
- POST /api-keys/{key_id}/activate - Reactivate revoked key (admin only)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db, require_admin, require_user
from models.api_key import APIKey
from types_definitions.api_key import (
    CreateAPIKeyRequest,
    APIKeyResponse,
    APIKeyListResponse,
    RevokeAPIKeyResponse,
)
from types_definitions.common import PaginationParams
from utils.crypto import decrypt_api_key
import controllers

router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"],
    responses={404: {"description": "Not found"}}
)


def _key_response(api_key: APIKey, plain_key: str | None = None) -> APIKeyResponse:
    """Build an APIKeyResponse, decrypting the stored key when available."""
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=plain_key if plain_key is not None else decrypt_api_key(api_key.key_encrypted),
        prefix=api_key.prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active,
        user_id=api_key.user_id,
    )


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    pagination: PaginationParams = Depends(),
    include_inactive: bool = False,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all API keys for AI agent authentication.

    Requires admin privileges. By default, only shows active keys.
    Each key's full value is included (decrypted server-side).
    """
    keys = controllers.api_key.list_api_keys(
        db=db,
        skip=pagination.skip,
        limit=pagination.limit,
        include_inactive=include_inactive
    )

    total = controllers.api_key.count_api_keys(
        db=db,
        include_inactive=include_inactive
    )

    return APIKeyListResponse(keys=[_key_response(k) for k in keys], total=total)


@router.get("/me", response_model=APIKeyListResponse)
async def list_my_api_keys(
    current_user = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    List the API keys assigned to the current user.

    Returns each active key's full value (decrypted server-side) so the
    assigned user can copy it from their settings. Keys created before
    encrypted storage return key=null. Admins should use GET /api-keys.
    """
    keys = controllers.api_key.list_api_keys_for_user(db=db, user_id=current_user.id)
    return APIKeyListResponse(keys=[_key_response(k) for k in keys], total=len(keys))


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new API key for AI agent authentication.

    Requires admin privileges. The full key is returned here and also stored
    encrypted, so it can be retrieved later from this list or by the assigned
    user via GET /api-keys/me.

    Format: `agent-esp-{32-char-hex}`

    Example: `agent-esp-a3f7b2d8e9c1f4a5b6d7e8f9a0b1c2d3`
    """
    try:
        api_key, plain_key = controllers.api_key.create_api_key(
            db=db,
            name=request.name,
            user_id=request.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return _key_response(api_key, plain_key=plain_key)


@router.delete("/{key_id}", response_model=RevokeAPIKeyResponse)
async def revoke_api_key(
    key_id: int,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Revoke (deactivate) an API key.
    
    Requires admin privileges. Revoked keys can be reactivated later if needed.
    """
    api_key = controllers.api_key.revoke_api_key(db=db, key_id=key_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    return RevokeAPIKeyResponse(revoked_key_id=key_id)


@router.post("/{key_id}/activate", response_model=APIKeyResponse)
async def activate_api_key(
    key_id: int,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reactivate a previously revoked API key.
    
    Requires admin privileges.
    """
    api_key = controllers.api_key.activate_api_key(db=db, key_id=key_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    return _key_response(api_key)
