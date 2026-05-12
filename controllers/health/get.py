"""
Health check controller.

This module contains the business logic for the health check endpoint.
"""

from typing import Dict, Any


def get_health_status() -> Dict[str, Any]:
    """
    Get the health status of the API.
    
    Returns:
        dict: Health status with status and message.
    """
    return {
        "status": "ok",
        "message": "Hello from Agent Espacio"
    }
