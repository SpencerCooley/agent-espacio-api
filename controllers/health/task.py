"""
Task trigger controller.

This module contains the business logic for triggering Celery tasks.
"""

from typing import Dict, Any
from celery_app.tasks import hello_world_task


def trigger_hello_task() -> Dict[str, Any]:
    """
    Trigger a hello world Celery task.
    
    This function queues a simple background task and returns the task ID.
    
    Returns:
        dict: Task queue status with task ID.
    """
    task = hello_world_task.delay()
    return {
        "status": "task_queued",
        "task_id": task.id,
        "message": "Hello world task has been queued"
    }
