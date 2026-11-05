import os
from urllib.parse import quote

from celery import Celery


def _redis_url(db: int) -> str:
    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    password = os.getenv("REDIS_PASSWORD")
    auth = f":{quote(password, safe='')}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db}"


broker_url = os.getenv("CELERY_BROKER_URL", _redis_url(0))
result_backend = os.getenv("CELERY_RESULT_BACKEND", _redis_url(1))

celery_app = Celery(
    "pesa_analyser",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.tasks.analysis",
        "app.tasks.payment",
        "app.tasks.report",
    ],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)
