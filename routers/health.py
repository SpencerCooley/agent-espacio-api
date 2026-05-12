"""
Health router.

This module defines the health check API routes.
All business logic is delegated to controllers.
"""

from fastapi import APIRouter

from controllers.health import get_health_status, trigger_hello_task, get_task_status

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """
    Health check endpoint.
    
    Returns a simple hello world message to verify the API is running.
    """
    return get_health_status()


@router.post("/task")
async def health_task():
    """
    Trigger a hello world Celery task.
    
    This endpoint demonstrates Celery integration by queuing
    a simple background task and returning the task ID.
    """
    return trigger_hello_task()


@router.get("/task/{task_id}")
async def health_task_status(task_id: str):
    """
    Get the status of a Celery task.
    
    Args:
        task_id: The ID of the Celery task to check.
        
    Returns:
        The current status and result of the task.
    """
    return get_task_status(task_id)
