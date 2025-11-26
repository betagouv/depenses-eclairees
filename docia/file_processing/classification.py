import logging

from celery import shared_task

from app.file_manager import DIC_CLASS_FILE_BY_NAME
from app.file_manager import classifier as processor

from .models import ProcessDocumentStep
from .utils import AbstractStepRunner

logger = logging.getLogger(__name__)


class ClassifyStepRunner(AbstractStepRunner):
    def process(self, step: ProcessDocumentStep):
        document = step.job.document
        file_path = document.file.name
        classification = processor.classify_file_with_llm(
            file_path,
            document.text,
            DIC_CLASS_FILE_BY_NAME,
        )
        document.classification = classification
        document.classification_type = "llm"
        document.save(update_fields=["classification", "classification_type"])


@shared_task(name="docia.classify_document")
def task_classify_document(step_id: str):
    runner = ClassifyStepRunner()
    return runner.run(step_id)
