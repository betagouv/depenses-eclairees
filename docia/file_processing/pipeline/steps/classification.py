import logging

from celery import shared_task

from docia.file_processing.models import ProcessDocumentStep
from docia.file_processing.pipeline.steps.base import AbstractStepRunner
from docia.file_processing.processor import classifier as processor
from docia.file_processing.processor.classifier import DIC_CLASS_FILE_BY_NAME

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
