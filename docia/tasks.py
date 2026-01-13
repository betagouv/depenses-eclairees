import logging

from celery import shared_task

from docia.file_processing.pipeline.tasks import (  # noqa: F401
    task_analyze_content,
    task_chunk_init_documents,
    task_classify_document,
    task_extract_text,
    task_launch_batch,
)

logger = logging.getLogger(__name__)


@shared_task(name="docia.add")
def add(x, y):
    logger.info("add %s + %s", x, y)
    return x + y
