import logging

from celery import shared_task

from docia.file_processing.models import ProcessDocumentStep, ProcessingStatus
from docia.file_processing.pipeline.steps.base import AbstractStepRunner
from docia.file_processing.pipeline.steps.exceptions import SkipStepException
from docia.file_processing.processor import text_extraction as processor
from docia.file_processing.processor.text_extraction import UnsupportedFileType
from docia.file_processing.processor.text_extraction.exceptions import FileSizeLimitException

logger = logging.getLogger(__name__)


class ExtractTextStepRunner(AbstractStepRunner):
    def process(self, step: ProcessDocumentStep):
        document = step.job.document
        file_path = document.file.name
        try:
            text, is_ocr, nb_words, nb_pages = processor.process_file(file_path, document.extension)
        except UnsupportedFileType as e:
            raise SkipStepException(str(e))
        except FileSizeLimitException as e:
            raise SkipStepException(str(e))

        if not text:
            raise Exception(f"Failed to extract text - empty result - {file_path}")

        document.text = text
        document.is_ocr = is_ocr
        document.nb_mot = nb_words
        document.nb_pages = nb_pages
        document.save(update_fields=["text", "is_ocr", "nb_mot", "nb_pages"])


@shared_task(name="docia.extract_text", queue="ocr")
def task_extract_text(step_id: str) -> ProcessingStatus:
    worker = ExtractTextStepRunner()
    return worker.run(step_id)
