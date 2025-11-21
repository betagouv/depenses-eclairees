import logging

from celery import shared_task

from app.processor import extraction_text_from_attachments as processor

from .models import ProcessDocumentStep, ProcessingStatus
from .utils import AbstractStepRunner

logger = logging.getLogger(__name__)


class ExtractTextStepRunner(AbstractStepRunner):
    def process(self, step: ProcessDocumentStep):
        document = step.job.document
        file_path = document.file.name
        text, is_ocr, nb_words = processor.process_file(file_path, document.extension)
        document.text = text
        document.is_ocr = is_ocr
        document.nb_mot = nb_words
        document.save(update_fields=["text", "is_ocr", "nb_mot"])


@shared_task(name="docia.extract_text", queue="heavy_cpu")
def task_extract_text(step_id: str) -> ProcessingStatus:
    worker = ExtractTextStepRunner()
    return worker.run(step_id)
