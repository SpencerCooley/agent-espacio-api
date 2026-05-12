from celery import Celery
from celery_app.config import CeleryConfig, CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "agentespacio",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["celery_app.tasks"]
)

# Load configuration
celery_app.config_from_object(CeleryConfig)

# Set namespace for environment variables
celery_app.conf.namespace = 'CELERY'

if __name__ == "__main__":
    celery_app.start()
