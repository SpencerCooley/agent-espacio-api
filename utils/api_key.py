"""
API key hashing utilities.
"""
import hashlib


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for storage using SHA-256.
    Only stores the hash, never the plain key.
    
    Args:
        api_key: Plain text API key (e.g., 'agent-esp-...')
        
    Returns:
        str: SHA-256 hash of the API key
    """
    return hashlib.sha256(api_key.encode('utf-8')).hexdigest()


def get_api_key_prefix(api_key: str) -> str:
    """
    Get the prefix of an API key for display purposes.
    Returns first 16 characters of the key.
    
    Args:
        api_key: Plain text API key
        
    Returns:
        str: First 16 characters of the key
    """
    return api_key[:16]
