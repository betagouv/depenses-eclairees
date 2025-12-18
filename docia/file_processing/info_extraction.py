import logging

from celery import shared_task

from app.processor import analyze_content as processor
from app.processor.attributes_query import ATTRIBUTES

from .models import ProcessDocumentStep
from .utils import AbstractStepRunner, SkipStepException

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


class ExtractInfoStepRunner(AbstractStepRunner):
    def process(self, step: ProcessDocumentStep):
        document = step.job.document
        file_path = document.file.name

        classification = document.classification
        target_classifications = step.job.batch.target_classifications

        if target_classifications is not None and classification not in target_classifications:
            raise SkipStepException(f"Not in target classifications: {classification}.")

        result = processor.analyze_file_text(
            file_path,
            document.relevant_content or document.text,
            ATTRIBUTES,
            document.classification,
        )
        document.llm_response = result["llm_response"]
        document.json_error = result["json_error"]
        document.save(update_fields=["llm_response", "json_error"])


@shared_task(name="docia.analyze_document")
def task_extract_info(step_id: str):
    runner = ExtractInfoStepRunner()
    return runner.run(step_id)
