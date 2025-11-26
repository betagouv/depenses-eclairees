import logging

from celery import shared_task

from .file_processing.classification import task_classify_document  # noqa: F401
from .file_processing.info_extraction import task_extract_info  # noqa: F401
from .file_processing.init_documents import task_chunk_init_documents  # noqa: F401
from .file_processing.pipeline import task_launch_batch  # noqa: F401
from .file_processing.text_extraction import task_extract_text  # noqa: F401

logger = logging.getLogger(__name__)


@shared_task(name="docia.add")
def add(x, y):
    logger.info("add %s + %s", x, y)
    return x + y
