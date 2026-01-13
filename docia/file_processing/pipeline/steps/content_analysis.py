import logging

from celery import shared_task

from docia.file_processing.processor import analyze_content as processor

from docia.file_processing.models import ProcessDocumentStep
from docia.file_processing.pipeline.steps.base import AbstractStepRunner, SkipStepException

logger = logging.getLogger(__name__)


SUPPORTED_DOCUMENT_TYPES = [
    "devis",
    "fiche_navette",
    "acte_engagement",
    "bon_de_commande",
    "avenant",
    "sous_traitance",
    "rib",
    "att_sirene",
    "kbis",
    "ccap",
]


class AnalyzeContentStepRunner(AbstractStepRunner):
    def process(self, step: ProcessDocumentStep):
        document = step.job.document

        classification = document.classification
        target_classifications = step.job.batch.target_classifications

        if target_classifications is not None and classification not in target_classifications:
            raise SkipStepException(f"Not in target classifications: {classification}.")

        result = processor.analyze_file_text(
            document.relevant_content or document.text,
            document.classification,
        )
        document.llm_response = result["llm_response"]
        document.json_error = result["json_error"]
        document.structured_data = result["structured_data"]
        document.save(update_fields=["llm_response", "structured_data", "json_error"])


@shared_task(name="docia.analyse_content")
def task_analyze_content(step_id: str):
    runner = AnalyzeContentStepRunner()
    return runner.run(step_id)
