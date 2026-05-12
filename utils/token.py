"""
Token generation utilities.
"""
import secrets
import string


def generate_token_string(length: int = 32) -> str:
    """
    Generate a secure random token string.
    Uses URL-safe base64 encoding.
    
    Args:
        length: Length of the token in bytes before encoding
        
    Returns:
        str: Secure random token string
    """
    return secrets.token_urlsafe(length)


def generate_api_key() -> str:
    """
    Generate a Stripe-style API key for agents.
    Format: agent-esp-{32-character-random-hex}
    
    Returns:
        str: API key in format 'agent-esp-{32-char-hex}'
    """
    random_part = secrets.token_hex(16)  # 32 hex characters
    return f"agent-esp-{random_part}"


def generate_reset_token() -> str:
    """
    Generate a secure password reset token.
    
    Returns:
        str: Secure random token string
    """
    return secrets.token_urlsafe(32)
