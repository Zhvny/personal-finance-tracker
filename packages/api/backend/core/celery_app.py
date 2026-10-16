import logging
import os

from celery import Celery

from packages.core.infrastructure.config import Config

# Configure logging
logger = logging.getLogger(__name__)

# Initialize config to load .env
Config.initialize()

# Redis URL for broker
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Celery result backend using Postgres
# Celery expects 'db+postgresql://' for the SQLAlchemy backend
POSTGRES_URL = f"db+postgresql://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"

celery_app = Celery(
    "finance_tracker",
    broker=REDIS_URL,
    backend=POSTGRES_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    worker_prefetch_multiplier=1, # One task at a time per worker for heavy ML/Analytics
)

# Optional: Configuration for Postgres backend to use specific schema
celery_app.conf.database_table_names = {
    'task': 'system.celery_taskmeta',
    'group': 'system.celery_groupmeta',
}

@celery_app.task(bind=True)
def debug_task(self):
    logger.info(f'Request: {self.request!r}')
    return "pong"

if __name__ == "__main__":
    celery_app.start()
