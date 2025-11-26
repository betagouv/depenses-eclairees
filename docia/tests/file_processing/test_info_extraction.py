from contextlib import contextmanager
from unittest.mock import patch

import pytest

from docia.file_processing.info_extraction import task_extract_info
from docia.file_processing.models import ProcessDocumentStepType, ProcessingStatus
from docia.tests.factories.file_processing import ProcessDocumentStepFactory


@contextmanager
def patch_extract_info():
    with patch("app.processor.analyze_content.analyze_file_text", autospec=True) as m:
        m.return_value = {
            "llm_response": {"nom": "Toto"},
            "json_error": None,
        }
        yield m


@pytest.mark.django_db
def test_task_extract_info():
    step = ProcessDocumentStepFactory(step_type=ProcessDocumentStepType.INFO_EXTRACTION)
    with patch_extract_info():
        task_extract_info(step.id)
    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.llm_response == {"nom": "Toto"}
    assert step.job.document.json_error is None


@pytest.mark.django_db
def test_do_process_based_on_classification():
    step = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.INFO_EXTRACTION,
        job__batch__target_classifications=["kbis"],
        job__document__classification="kbis",
    )
    with patch_extract_info():
        task_extract_info(step.id)

    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.llm_response == {"nom": "Toto"}
    assert step.job.document.json_error is None


@pytest.mark.django_db
def test_skip_based_on_classification():
    step = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.INFO_EXTRACTION,
        job__batch__target_classifications=["kbis"],
        job__document__classification="devis",
    )
    with patch_extract_info():
        task_extract_info(step.id)

    step.refresh_from_db()
    assert step.status == ProcessingStatus.SKIPPED
    assert step.error == ""
    assert step.job.document.llm_response is None
    assert step.job.document.json_error is None
