import logging

from celery import shared_task

from docia.file_processing.pipeline.tasks import *  # noqa: F403

logger = logging.getLogger(__name__)


@shared_task(name="docia.add")
def add(x, y):
    logger.info("add %s + %s", x, y)
    return x + y
