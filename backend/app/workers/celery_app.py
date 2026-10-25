from celery import Celery

from app.core.config import Settings

settings = Settings()
celery_app = Celery("cisrice", broker=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
)
# No business tasks until PostgreSQL durable job records and idempotent handlers exist.
