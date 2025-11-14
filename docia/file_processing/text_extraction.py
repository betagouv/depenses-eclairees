import logging
import traceback

from django.db.transaction import atomic

from celery import chord, shared_task
from celery.result import AsyncResult

from app.processor import extraction_text_from_attachments as processing
from docia.file_processing.models import BatchTextExtraction, FileTextExtraction, TaskStatus
from docia.models import DataAttachment

logger = logging.getLogger(__name__)


def extract_text_for_folder(folder: str) -> tuple[BatchTextExtraction, AsyncResult]:
    """
    Create a batch text extraction task for all documents in a given folder.

    Args:
        folder (str): The folder path to process documents from

    Returns:
        tuple: A tuple containing (BatchTextExtraction object, Celery task result)
    """
    with atomic():
        batch = BatchTextExtraction.objects.create(folder=folder, status=TaskStatus.STARTED)
        extracts = []
        for document in DataAttachment.objects.filter(file__startswith=folder):
            extract = FileTextExtraction(
                batch=batch,
                document=document,
                status=TaskStatus.PENDING,
            )
            extracts.append(extract)
        batch.filetextextraction_set.bulk_create(extracts)
    r = chord(task_extract_text.s(extract.id) for extract in extracts)(task_finalize_batch.s(batch.id))
    return batch, r


def extract_text(document: DataAttachment) -> tuple[FileTextExtraction, AsyncResult]:
    """
    Create a text extraction task for a single document.

    Args:
        document (DataAttachment): The document object to extract text from

    Returns:
        tuple: A tuple containing (FileTextExtraction object, Celery task result)
    """
    extract = FileTextExtraction.objects.create(
        document=document,
        status=TaskStatus.PENDING,
    )
    r = task_extract_text.delay(extract.id)
    return extract, r


@shared_task
def task_extract_text(extract_id: str):
    """
    Celery task to extract text from a document.

    Args:
        extract_id (str): The ID of the FileTextExtraction object to process

    Returns:
        TaskStatus: The final status of the text extraction task
    """
    with atomic():
        extract = FileTextExtraction.objects.select_for_update(nowait=True).get(id=extract_id)

        if extract.status != TaskStatus.PENDING:
            logger.info(f"Task {extract_id} ({extract.document.file.name}) already processed")
            return

        document = extract.document
        file_path = document.file.name

        try:
            text, is_ocr, nb_words = processing.process_file(file_path, document.extension)
        except Exception:
            logger.exception("Error during text extraction %s", file_path)
            extract.status = TaskStatus.FAILURE
            extract.error = traceback.format_exc()
            extract.save()
        else:
            document.text = text
            document.is_ocr = is_ocr
            document.nb_mot = nb_words
            document.save()
            extract.status = TaskStatus.SUCCESS
            extract.save()

    return extract.status


@shared_task
def task_finalize_batch(extract_results: list[TaskStatus], batch_id: str) -> TaskStatus:
    """
    Celery task to finalize a batch text extraction process.
    Set the status to either SUCCESS or FAILURE based on the status of all tasks in the batch.

    Args:
        batch_id (str): The ID of the BatchTextExtraction to finalize

    Returns:
        TaskStatus: The final status of the batch text extraction task
    """
    with atomic():
        batch = BatchTextExtraction.objects.select_for_update(nowait=True).get(id=batch_id)

        if batch.filetextextraction_set.filter(status__in=(TaskStatus.PENDING, TaskStatus.STARTED)).exists():
            logger.error(f"Batch {batch_id} not finished yet")
            raise ValueError(f"Batch not finished yet. (batch_id={batch.id})")
        elif batch.filetextextraction_set.filter(status=TaskStatus.FAILURE).exists():
            batch.status = TaskStatus.FAILURE
        else:
            batch.status = TaskStatus.SUCCESS

        batch.save()

    return batch.status
