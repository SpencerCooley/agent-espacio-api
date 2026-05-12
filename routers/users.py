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
