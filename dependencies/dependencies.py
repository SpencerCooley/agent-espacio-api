"""
Dependency injection functions for authentication and database.
"""
import os
import sys
from typing import Generator, Optional
from datetime import datetime

from fastapi import Header, Depends, status, Request, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Add project root to path for imports
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from models.enums import RoleEnum
from models.user import User
from models.token import Token
from models.api_key import APIKey
from utils.api_key import hash_api_key


# ============================================================================
# Database Dependency
# ============================================================================

async def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.
    
    Yields a SQLAlchemy session that is automatically closed after use.
    """
    DATABASE_URL = os.environ.get('DATABASE_URL', 
        'postgresql://agentespacio:agentespacio@db:5432/agentespacio_db')
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# OAuth2 Schemes
# ============================================================================

# Standard OAuth2 scheme for protected endpoints
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    scheme_name="JWT"
)

# Optional OAuth2 scheme for endpoints that work with/without auth
class OptionalOAuth2PasswordBearer(OAuth2PasswordBearer):
    """OAuth2 scheme that doesn't raise errors when no token is provided."""
    async def __call__(self, request: Request) -> Optional[str]:
        try:
            return await super().__call__(request)
        except HTTPException:
            return None

oauth2_scheme_optional = OptionalOAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False
)


# ============================================================================
# User Authentication Dependencies
# ============================================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Validate bearer token and return authenticated user.
    
    Args:
        token: Bearer token from Authorization header
        db: Database session
        
    Returns:
        User: Authenticated user object
        
    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    db_token = db.query(Token).filter(Token.token == token).first()
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not db_token.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is inactive",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check if token is expired (7 days from creation)
    if db_token.expires_at and db_token.expires_at < datetime.utcnow():
        db_token.is_active = False
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return db_token.user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional user authentication - returns User if authenticated, None otherwise.
    
    Args:
        token: Optional bearer token from Authorization header
        db: Database session
        
    Returns:
        Optional[User]: User if authenticated, None otherwise
    """
    if not token:
        return None
    
    try:
        db_token = db.query(Token).filter(Token.token == token).first()
        
        if not db_token or not db_token.is_active:
            return None
        
        if db_token.expires_at and db_token.expires_at < datetime.utcnow():
            db_token.is_active = False
            db.commit()
            return None
        
        return db_token.user
    except Exception:
        return None


# ============================================================================
# API Key Authentication Dependencies
# ============================================================================

def get_current_api_key(
    x_agent_key: str = Header(..., alias="X-Agent-Key"),
    db: Session = Depends(get_db)
) -> APIKey:
    """
    Validate X-Agent-Key header and return API key.
    
    Args:
        x_agent_key: API key from X-Agent-Key header
        db: Database session
        
    Returns:
        APIKey: Validated API key object
        
    Raises:
        HTTPException: 401 if API key is invalid
    """
    # Hash the provided key and compare with stored hash
    key_hash = hash_api_key(x_agent_key)
    api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    if not api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has been revoked"
        )
    
    return api_key


def get_current_api_key_optional(
    x_agent_key: Optional[str] = Header(None, alias="X-Agent-Key"),
    db: Session = Depends(get_db)
) -> Optional[APIKey]:
    """
    Optional API key authentication - returns APIKey if valid, None otherwise.
    
    Args:
        x_agent_key: Optional API key from X-Agent-Key header
        db: Database session
        
    Returns:
        Optional[APIKey]: APIKey if valid, None otherwise
    """
    if not x_agent_key:
        return None
    
    try:
        key_hash = hash_api_key(x_agent_key)
        api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
        
        if not api_key or not api_key.is_active:
            return None
        
        return api_key
    except Exception:
        return None


# ============================================================================
# Permission Dependencies
# ============================================================================

def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require that the current user has admin role.
    
    Args:
        current_user: Authenticated user from get_current_user
        
    Returns:
        User: Admin user object
        
    Raises:
        HTTPException: 403 if user is not admin
    """
    if current_user.role != RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require any authenticated user (admin or regular user).
    
    Args:
        current_user: Authenticated user from get_current_user
        
    Returns:
        User: Authenticated user object
    """
    return current_user


def allow_agent_api_key(
    api_key: APIKey = Depends(get_current_api_key)
) -> APIKey:
    """
    Allow access with a valid API key (for AI agents).
    
    Args:
        api_key: Validated API key from get_current_api_key
        
    Returns:
        APIKey: Valid API key object
    """
    return api_key


def require_auth(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    x_agent_key: Optional[str] = Header(None, alias="X-Agent-Key"),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Unified authentication - accepts either Bearer token or X-Agent-Key.
    
    Args:
        token: Optional Bearer token from Authorization header
        x_agent_key: Optional API key from X-Agent-Key header
        db: Database session
        
    Returns:
        Optional[User]: Authenticated user if using Bearer token, None if using API key
        
    Raises:
        HTTPException: 401 if neither auth method is valid
    """
    # Try Bearer token first
    if token:
        db_token = db.query(Token).filter(Token.token == token).first()
        
        if db_token and db_token.is_active:
            if not db_token.expires_at or db_token.expires_at >= datetime.utcnow():
                return db_token.user
    
    # Try API key
    if x_agent_key:
        key_hash = hash_api_key(x_agent_key)
        api_key = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if api_key:
            # API key is valid but has no associated user
            return None
    
    # Neither auth method succeeded
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication",
        headers={"WWW-Authenticate": "Bearer, X-Agent-Key"}
    )


def get_ws_auth(token: Optional[str] = None, db: Session = None) -> Optional[User]:
    """
    WebSocket authentication - validate Bearer token from WebSocket handshake.
    
    Args:
        token: Bearer token from Authorization header (without 'Bearer ' prefix)
        db: Database session (caller must provide one)
        
    Returns:
        Optional[User]: Authenticated user if valid, None otherwise
    """
    if not token or not db:
        return None
    
    db_token = db.query(Token).filter(Token.token == token).first()
    
    if db_token and db_token.is_active:
        if not db_token.expires_at or db_token.expires_at >= datetime.utcnow():
            return db_token.user
    
    return None
