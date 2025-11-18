import logging

from celery import shared_task
from celery.result import AsyncResult

from app.processor import analyze_content as processor
from app.processor.attributes_query import ATTRIBUTES
from docia.models import DataAttachment

from .models import BatchJob, DocumentJob, JobName
from .utils import AbstractJobWorker, launch_batch, launch_document_job

logger = logging.getLogger(__name__)


def analyze_documents_in_folder(folder: str) -> tuple[BatchJob, AsyncResult]:
    return launch_batch(
        JobName.ANALYZE,
        folder,
        task_analyze_document,
    )


def analyze_document(document: DataAttachment) -> tuple[DocumentJob, AsyncResult]:
    return launch_document_job(JobName.ANALYZE, document, task_analyze_document)


class AnalyzeDocumentJobWorker(AbstractJobWorker):
    def process(self, job):
        document = job.document
        file_path = document.file.name

        result = processor.analyze_file_text(
            file_path,
            document.relevant_content or document.text,
            ATTRIBUTES,
            document.classification,
        )
        document.llm_response = result["llm_response"]
        document.json_error = result["json_error"]
        document.save(update_fields=["llm_response", "json_error"])


@shared_task
def task_analyze_document(job_id: str):
    runner = AnalyzeDocumentJobWorker()
    return runner.run(job_id)
