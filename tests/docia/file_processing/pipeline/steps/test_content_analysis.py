from contextlib import contextmanager
from unittest.mock import patch

import pytest

from docia.file_processing.models import ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.pipeline.steps.content_analysis import task_analyze_content
from tests.factories.file_processing import ProcessDocumentStepFactory


@contextmanager
def patch_analyze_content():
    with patch("docia.file_processing.processor.analyze_content.analyze_file_text", autospec=True) as m:
        m.return_value = {
            "llm_response": {"nom": "Toto  ."},
            "structured_data": {"nom": "Toto"},
            "json_error": None,
        }
        yield m


@pytest.mark.django_db
def test_task_analyze_content():
    step = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.CONTENT_ANALYSIS, job__document__classification="devis"
    )
    with patch_analyze_content():
        task_analyze_content(step.id)
    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.llm_response == {"nom": "Toto  ."}
    assert step.job.document.structured_data == {"nom": "Toto"}
    assert step.job.document.json_error is None


@pytest.mark.django_db
def test_do_process_based_on_classification():
    step = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.CONTENT_ANALYSIS,
        job__batch__target_classifications=["kbis"],
        job__document__classification="kbis",
    )
    with patch_analyze_content():
        task_analyze_content(step.id)

    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.llm_response == {"nom": "Toto  ."}
    assert step.job.document.structured_data == {"nom": "Toto"}
    assert step.job.document.json_error is None


@pytest.mark.django_db
def test_skip_based_on_classification():
    step = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.CONTENT_ANALYSIS,
        job__batch__target_classifications=["kbis"],
        job__document__classification="devis",
    )
    with patch_analyze_content():
        task_analyze_content(step.id)

    step.refresh_from_db()
    assert step.status == ProcessingStatus.SKIPPED
    assert step.error == ""
    assert step.job.document.llm_response is None
    assert step.job.document.structured_data is None
    assert step.job.document.json_error is None
