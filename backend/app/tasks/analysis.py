import asyncio

from app.tasks.celery_app import celery_app


@celery_app.task(
    name="app.tasks.analysis.process_analysis_task",
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_analysis_task(
    file_id: str,
    file_path: str,
    encrypted_password: str | None = None,
) -> None:
    from app.routers.upload import process_analysis

    asyncio.run(process_analysis(file_id, file_path, encrypted_password))
