"""
API key controller - list API keys.
"""
from typing import List

from sqlalchemy.orm import Session

from models.api_key import APIKey


def list_api_keys(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False
) -> List[APIKey]:
    """
    List all API keys.
    
    Args:
        db: Database session
        skip: Number of keys to skip (pagination)
        limit: Maximum number of keys to return (pagination)
        include_inactive: Whether to include revoked/inactive keys
        
    Returns:
        List of APIKey objects
    """
    query = db.query(APIKey)
    
    if not include_inactive:
        query = query.filter(APIKey.is_active == True)
    
    return query.order_by(APIKey.created_at.desc()).offset(skip).limit(limit).all()


def count_api_keys(db: Session, include_inactive: bool = False) -> int:
    """
    Count total number of API keys.
    
    Args:
        db: Database session
        include_inactive: Whether to include revoked/inactive keys
        
    Returns:
        Total count of API keys
    """
    query = db.query(APIKey)
    
    if not include_inactive:
        query = query.filter(APIKey.is_active == True)
    
    return query.count()
