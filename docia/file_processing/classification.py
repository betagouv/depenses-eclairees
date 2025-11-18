import logging

from celery import shared_task
from celery.result import AsyncResult

from app.file_manager import DIC_CLASS_FILE_BY_NAME
from app.file_manager import classifier as processor
from docia.models import DataAttachment

from .models import BatchJob, DocumentJob, JobName
from .utils import AbstractJobWorker, launch_batch, launch_document_job

logger = logging.getLogger(__name__)


def classify_documents_in_folder(folder: str) -> tuple[BatchJob, AsyncResult]:
    return launch_batch(
        JobName.CLASSIFICATION,
        folder,
        task_classify_document,
    )


def classify_document(document: DataAttachment) -> tuple[DocumentJob, AsyncResult]:
    return launch_document_job(JobName.CLASSIFICATION, document, task_classify_document)


class DocumentClassificationJobWorker(AbstractJobWorker):
    def process(self, job):
        document = job.document
        file_path = document.file.name
        classification = processor.classify_file_with_llm(
            file_path,
            document.text,
            DIC_CLASS_FILE_BY_NAME,
        )
        document.classification = classification
        document.classification_type = "llm"
        document.save(update_fields=["classification", "classification_type"])


@shared_task
def task_classify_document(job_id: str):
    runner = DocumentClassificationJobWorker()
    return runner.run(job_id)
