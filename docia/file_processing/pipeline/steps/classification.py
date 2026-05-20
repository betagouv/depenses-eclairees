import logging

from django.utils import timezone

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
        result = processor.classify_file_with_llm(
            file_path,
            document.text,
            DIC_CLASS_FILE_BY_NAME,
        )
        document.classification = result.classification
        document.classification_type = "llm"
        document.classified_at = timezone.now()
        document.classification_prompt_tokens_count = result.usage.prompt_tokens
        document.classification_completion_tokens_count = result.usage.completion_tokens
        document.save(
            update_fields=[
                "classification",
                "classification_type",
                "classified_at",
                "classification_prompt_tokens_count",
                "classification_completion_tokens_count",
            ]
        )


@shared_task(name="docia.classify_document")
def task_classify_document(step_id: str):
    runner = ClassifyStepRunner()
    return runner.run(step_id)
