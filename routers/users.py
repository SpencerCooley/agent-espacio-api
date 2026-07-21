"""
Users router.

Endpoints for user management (admin only for most operations):
- GET /users/me - Get current user
- GET /users - List all users
- POST /users - Create new user
- PUT /users/{user_id} - Update user
- DELETE /users/{user_id} - Delete user
- POST /users/{user_id}/reset-password - Admin reset password
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session

from dependencies.dependencies import (
    get_db,
    get_current_user,
    require_admin,
    require_user,
)
from models.user import User
from models.enums import RoleEnum
from types_definitions.user import (
    CreateUserRequest,
    UpdateUserRequest,
    PublicUser,
    UserListResponse,
    DeleteUserResponse,
)
from types_definitions.auth import AdminPasswordResetRequest
from types_definitions.common import PaginationParams
import controllers

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}}
)


@router.get("/me", response_model=PublicUser)
async def get_current_user_info(
    current_user: PublicUser = Depends(require_user)
):
    """
    Get information about the currently authenticated user.
    """
    return current_user


@router.get("", response_model=UserListResponse)
async def list_users(
    pagination: PaginationParams = Depends(),
    current_user: PublicUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users in the system.
    
    Requires admin privileges. Supports pagination.
    """
    users = controllers.user.list_users(
        db=db,
        skip=pagination.skip,
        limit=pagination.limit
    )
    
    total = controllers.user.count_users(db=db)
    
    return UserListResponse(users=users, total=total)


@router.post("", response_model=PublicUser, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    current_user: PublicUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new user.
    
    Requires admin privileges. If no admin exists, this will be the first admin.
    """
    user = controllers.user.create_user(
        db=db,
        email=request.email,
        password=request.password,
        role=request.role
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists"
        )
    
    return user


@router.put("/{user_id}", response_model=PublicUser)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    current_user: PublicUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update a user.
    
    Requires admin privileges. Can update email, password, or role.
    """
    user = controllers.user.update_user(
        db=db,
        user_id=user_id,
        email=request.email,
        password=request.password,
        role=request.role
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or email already in use"
        )
    
    return user


@router.delete("/{user_id}", response_model=DeleteUserResponse)
async def delete_user(
    user_id: int,
    current_user: PublicUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a user and all associated data (tokens, reset tokens).
    
    Requires admin privileges. This operation cannot be undone.
    """
    # Prevent self-deletion
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    deleted_id = controllers.user.delete_user(db=db, user_id=user_id)
    
    if not deleted_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return DeleteUserResponse(deleted_user_id=deleted_id)


@router.post("/{user_id}/reset-password")
async def admin_reset_password(
    user_id: int,
    request: AdminPasswordResetRequest,
    current_user: PublicUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reset a user's password (admin only).
    
    The user will be logged out from all sessions and must login with the new password.
    """
    user = controllers.user.admin_reset_password(
        db=db,
        user_id=user_id,
        new_password=request.new_password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": f"Password reset successfully for {user.email}"}


# ============================================================================
# SSH Key Management
# ============================================================================

import hashlib

from pydantic import BaseModel, Field
from models.repo_ssh_key import RepoSshKey


class AddSshKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Descriptive name for this key")
    public_key: str = Field(..., min_length=1, description="OpenSSH public key string")


class SshKeyResponse(BaseModel):
    id: int = Field(..., description="Key ID")
    name: str = Field(..., description="Key name")
    fingerprint: str = Field(..., description="SHA256 fingerprint")
    created_at: str = Field(..., description="Creation timestamp ISO")

    class Config:
        from_attributes = True


class SshKeyListResponse(BaseModel):
    keys: list[SshKeyResponse] = Field(default_factory=list, description="SSH keys")


def _compute_fingerprint(public_key: str) -> str:
    """Compute SHA256 fingerprint of an SSH public key."""
    # Extract the base64 key part (skip prefix like 'ssh-ed25519 ')
    parts = public_key.strip().split()
    if len(parts) >= 2:
        key_data = parts[1]
    else:
        key_data = parts[0]
    
    decoded = key_data.encode() if isinstance(key_data, str) else key_data
    # Properly decode base64
    import base64
    try:
        key_bytes = base64.b64decode(decoded)
        digest = hashlib.sha256(key_bytes).digest()
        fingerprint = base64.b64encode(digest).rstrip(b'=').decode()
        return f"SHA256:{fingerprint}"
    except Exception:
        # Fallback: hash the raw string
        digest = hashlib.sha256(decoded.encode() if isinstance(decoded, str) else decoded).digest()
        fingerprint = base64.b64encode(digest).rstrip(b'=').decode()
        return f"SHA256:{fingerprint}"


@router.post("/me/ssh-keys", response_model=SshKeyResponse, status_code=status.HTTP_201_CREATED)
async def add_ssh_key(
    request: AddSshKeyRequest,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Add an SSH public key for git repository access.
    
    The git container queries the database directly via AuthorizedKeysCommand.
    """
    fingerprint = _compute_fingerprint(request.public_key)
    
    # Check if key already exists
    existing = db.query(RepoSshKey).filter(
        RepoSshKey.user_id == current_user.id,
        RepoSshKey.fingerprint == fingerprint
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This SSH key is already registered"
        )
    
    ssh_key = RepoSshKey(
        user_id=current_user.id,
        name=request.name,
        public_key=request.public_key.strip(),
        fingerprint=fingerprint,
    )
    
    db.add(ssh_key)
    db.commit()
    db.refresh(ssh_key)
    
    return SshKeyResponse(
        id=ssh_key.id,
        name=ssh_key.name,
        fingerprint=ssh_key.fingerprint,
        created_at=ssh_key.created_at.isoformat() if ssh_key.created_at else "",
    )


@router.get("/me/ssh-keys", response_model=SshKeyListResponse)
async def list_ssh_keys(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    List SSH keys for the current user.
    """
    keys = db.query(RepoSshKey).filter(RepoSshKey.user_id == current_user.id).all()
    
    return SshKeyListResponse(
        keys=[
            SshKeyResponse(
                id=k.id,
                name=k.name,
                fingerprint=k.fingerprint,
                created_at=k.created_at.isoformat() if k.created_at else "",
            )
            for k in keys
        ]
    )


@router.delete("/me/ssh-keys/{key_id}")
async def delete_ssh_key(
    key_id: int,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Delete an SSH key.
    
    Users can only delete their own keys.
    """
    key = db.query(RepoSshKey).filter(
        RepoSshKey.id == key_id,
        RepoSshKey.user_id == current_user.id
    ).first()
    
    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSH key not found"
        )
    
    db.delete(key)
    db.commit()
    
    return {"message": "SSH key deleted successfully"}
