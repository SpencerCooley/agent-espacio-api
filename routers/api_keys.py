"""
API Keys router.

Endpoints for API key management (admin only):
- GET /api-keys - List all API keys
- POST /api-keys - Create new API key
- DELETE /api-keys/{key_id} - Revoke API key
- POST /api-keys/{key_id}/activate - Reactivate revoked key
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db, require_admin
from types_definitions.api_key import (
    CreateAPIKeyRequest,
    APIKeyResponse,
    APIKeyListResponse,
    RevokeAPIKeyResponse,
)
from types_definitions.common import PaginationParams
import controllers

router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"],
    responses={404: {"description": "Not found"}}
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
    
    return APIKeyListResponse(keys=keys, total=total)


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new API key for AI agent authentication.
    
    Requires admin privileges. **Important**: The full API key is shown only once 
    on creation. Store it securely - it cannot be retrieved again!
    
    Format: `agent-esp-{32-char-hex}`
    
    Example: `agent-esp-a3f7b2d8e9c1f4a5b6d7e8f9a0b1c2d3`
    """
    api_key, plain_key = controllers.api_key.create_api_key(
        db=db,
        name=request.name
    )
    
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=plain_key,  # Only shown once!
        prefix=api_key.prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active
    )


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
    
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=None,  # Never show the full key after creation
        prefix=api_key.prefix,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        is_active=api_key.is_active
    )
