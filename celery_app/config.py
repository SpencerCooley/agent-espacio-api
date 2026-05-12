# Celery configuration module
from config.settings import get_settings

settings = get_settings()

# Celery broker and backend URLs
CELERY_BROKER_URL = settings.celery_broker_url
CELERY_RESULT_BACKEND = settings.celery_result_backend


class CeleryConfig:
    """Celery configuration class."""
    
    # Broker configuration
    broker_url = CELERY_BROKER_URL
    result_backend = CELERY_RESULT_BACKEND
    
    # Serialization
    task_serializer = 'json'
    accept_content = ['json']
    result_serializer = 'json'
    
    # Timezone
    timezone = 'UTC'
    enable_utc = True
    
    # Task execution
    task_track_started = True
    task_time_limit = 30 * 60  # 30 minutes
    worker_prefetch_multiplier = 1
