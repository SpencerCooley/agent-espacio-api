"""
Authentication router.

Endpoints for user authentication:
- POST /auth/login - Login with credentials
- POST /auth/logout - Logout and invalidate token
- GET /auth/validate - Validate token
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db, get_current_user, oauth2_scheme
from types_definitions.auth import (
    UserCredentials,
    AuthTokenWithUser,
    TokenValidationResponse,
    LogoutResponse,
)
import controllers

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
    responses={404: {"description": "Not found"}}
)


@router.post("/login", response_model=AuthTokenWithUser)
async def login(
    credentials: UserCredentials,
    db: Session = Depends(get_db)
):
    """
    Login with email and password to receive an authentication token.
    
    The token expires after 7 days and must be included in the 
    Authorization header as: Bearer <token>
    """
    result = controllers.auth.login(
        db=db,
        email=credentials.email,
        password=credentials.password
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return result


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    Logout and invalidate the current authentication token.
    
    After logout, the token cannot be used for authentication again.
    """
    success = controllers.auth.logout(db=db, token_string=token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token"
        )
    
    return {"message": "Logged out successfully"}


@router.get("/validate", response_model=TokenValidationResponse)
async def validate_token(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    Validate the current authentication token.
    
    Returns whether the token is valid and the associated user information.
    Useful for client-side token validation checks.
    """
    result = controllers.auth.validate_token(db=db, token_string=token)
    
    return TokenValidationResponse(
        valid=result["valid"],
        user=result["user"],
        message=result["message"]
    )
