"""
Users router.

Endpoints for user management (admin only for most operations):
- GET /users/me - Get current user
- POST /users/me/change-password - Change own password
- GET /users - List all users
- POST /users - Create new user
- PUT /users/{user_id} - Update user
- DELETE /users/{user_id} - Delete user
- POST /users/{user_id}/reset-password - Admin reset password

SSH key management has moved to the SSH Keys router (/ssh-keys).
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from dependencies.dependencies import (
    get_db,
    get_current_user,
    require_admin,
    require_user,
)
from models.user import User
from models.enums import RoleEnum
from models.folder import Folder
from types_definitions.user import (
    CreateUserRequest,
    UpdateUserRequest,
    PublicUser,
    UserListResponse,
    DeleteUserResponse,
)
from types_definitions.auth import AdminPasswordResetRequest, PasswordChangeRequest
from types_definitions.common import PaginationParams
import controllers


class AddScopeRequest(BaseModel):
    folder_id: UUID = Field(..., description="Folder to grant access to")


class ScopeFolderResponse(BaseModel):
    folder_id: UUID
    name: str
    path: str
    is_root: bool
    created_at: Optional[str] = None


class ScopeListResponse(BaseModel):
    scopes: List[ScopeFolderResponse]
    total: int

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


@router.post("/me/change-password")
async def change_own_password(
    request: PasswordChangeRequest,
    current_user: PublicUser = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Change the currently authenticated user's own password.

    Requires the current password for verification. All sessions are
    invalidated on success, so the user must log in again.
    """
    user = controllers.user.change_own_password(
        db=db,
        user_id=current_user.id,
        current_password=request.current_password,
        new_password=request.new_password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    return {"message": "Password changed successfully. Please log in again."}


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


@router.get("/{user_id}/scopes", response_model=ScopeListResponse)
async def list_user_scopes(
    user_id: int,
    current_user: PublicUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List folder grants for a user.

    Admin only. Each grant gives access to that folder and all descendants.
    """
    user = controllers.user.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    rows = controllers.user.list_user_scopes(db, user_id)
    scopes: List[ScopeFolderResponse] = []
    for row in rows:
        folder = db.query(Folder).filter(Folder.id == row.folder_id).first()
        if not folder:
            continue
        scopes.append(
            ScopeFolderResponse(
                folder_id=folder.id,
                name=folder.name,
                path=folder.path,
                is_root=folder.is_root,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
        )

    return ScopeListResponse(scopes=scopes, total=len(scopes))


@router.post("/{user_id}/scopes", response_model=ScopeFolderResponse, status_code=status.HTTP_201_CREATED)
async def add_user_scope(
    user_id: int,
    request: AddScopeRequest,
    current_user: PublicUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Grant a user access to a folder (and its descendants).

    Admin only. Idempotent if the grant already exists.
    """
    scope_row = controllers.user.add_user_scope(db, user_id, request.folder_id)
    if not scope_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User or folder not found",
        )

    folder = db.query(Folder).filter(Folder.id == scope_row.folder_id).first()
    return ScopeFolderResponse(
        folder_id=folder.id,
        name=folder.name,
        path=folder.path,
        is_root=folder.is_root,
        created_at=scope_row.created_at.isoformat() if scope_row.created_at else None,
    )


@router.delete("/{user_id}/scopes/{folder_id}")
async def remove_user_scope(
    user_id: int,
    folder_id: UUID,
    current_user: PublicUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Remove a folder grant from a user.

    Admin only.
    """
    removed = controllers.user.remove_user_scope(db, user_id, folder_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scope grant not found",
        )
    return {"removed": True, "user_id": user_id, "folder_id": str(folder_id)}
