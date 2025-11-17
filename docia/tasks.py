import logging

from celery import shared_task

from .file_processing.text_extraction import task_extract_text, task_finalize_batch  # noqa: F401

logger = logging.getLogger(__name__)


@shared_task
def add(x, y):
    logger.info("add %s + %s", x, y)
    return x + y
