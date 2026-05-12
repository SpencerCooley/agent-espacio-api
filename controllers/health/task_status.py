"""
Task status controller.

This module contains the business logic for checking Celery task status.
"""

from typing import Dict, Any, Optional
from celery_app.celery_app import celery_app


def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status of a Celery task.
    
    Args:
        task_id: The ID of the Celery task to check.
        
    Returns:
        dict: Task status, result (if ready), and task ID.
    """
    task_result = celery_app.AsyncResult(task_id)
    
    result: Optional[Any] = None
    if task_result.ready():
        result = task_result.result
    
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": result
    }
