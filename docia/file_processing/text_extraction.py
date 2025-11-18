import logging

from celery import shared_task
from celery.result import AsyncResult

from app.processor import extraction_text_from_attachments as processor
from docia.models import DataAttachment

from .models import BatchJob, DocumentJob, JobName, JobStatus
from .utils import AbstractJobWorker, launch_batch, launch_document_job

logger = logging.getLogger(__name__)


def extract_text_for_folder(folder: str) -> tuple[BatchJob, AsyncResult]:
    return launch_batch(
        JobName.TEXT_EXTRACTION,
        folder,
        task_extract_text,
    )


def extract_text(document: DataAttachment) -> tuple[DocumentJob, AsyncResult]:
    return launch_document_job(JobName.TEXT_EXTRACTION, document, task_extract_text)


class ExtractTextJobWorker(AbstractJobWorker):
    def process(self, job):
        document = job.document
        file_path = document.file.name
        text, is_ocr, nb_words = processor.process_file(file_path, document.extension)
        document.text = text
        document.is_ocr = is_ocr
        document.nb_mot = nb_words
        document.save(update_fields=["text", "is_ocr", "nb_mot"])


@shared_task
def task_extract_text(job_id: str) -> JobStatus:
    worker = ExtractTextJobWorker()
    return worker.run(job_id)
