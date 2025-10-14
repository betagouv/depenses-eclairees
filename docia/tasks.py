import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def add(x, y):
    logger.info("add %s + %s", x, y)
    return x + y
