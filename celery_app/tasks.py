from celery_app.celery_app import celery_app


@celery_app.task(bind=True)
def hello_world_task(self):
    """
    A simple hello world Celery task.
    
    Returns:
        dict: A greeting message with task ID.
    """
    return {
        "message": "Hello from Agent Espacio Celery!",
        "task_id": self.request.id,
        "status": "success"
    }
