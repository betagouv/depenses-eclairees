from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import freezegun
import pytest

from docia.file_processing.llm.client import LLMUsage
from docia.file_processing.models import ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.pipeline.steps.content_analysis import task_analyze_content
from docia.file_processing.processor.analyze_content import AnalyzeResult
from tests.factories.file_processing import ProcessDocumentStepFactory


@contextmanager
def patch_analyze_content():
    with patch("docia.file_processing.processor.analyze_content.analyze_file_text", autospec=True) as m:
        m.return_value = AnalyzeResult(
            llm_response={"nom": "Toto  ."},
            structured_data={"nom": "Toto"},
            usage=LLMUsage(prompt_tokens=17, completion_tokens=11),
        )
        yield m


@pytest.mark.django_db
def test_task_analyze_content():
    step = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.CONTENT_ANALYSIS, job__document__classification="devis"
    )
    last_updated_at = step.job.document.updated_at
    frozen_time = last_updated_at + timedelta(days=30)

    with freezegun.freeze_time(frozen_time):
        with patch_analyze_content():
            task_analyze_content(step.id)

    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.llm_response == {"nom": "Toto  ."}
    assert step.job.document.structured_data == {"nom": "Toto"}
    assert step.job.document.analyzed_at == frozen_time
    assert step.job.document.analyze_prompt_tokens_count == 17
    assert step.job.document.analyze_completion_tokens_count == 11
    assert step.job.document.updated_at == frozen_time


@pytest.mark.django_db
def test_do_process_based_on_classification():
    step = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.CONTENT_ANALYSIS,
        job__batch__target_classifications=["kbis"],
        job__document__classification="kbis",
    )
    frozen_time = datetime(2023, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    with freezegun.freeze_time(frozen_time):
        with patch_analyze_content():
            task_analyze_content(step.id)

    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.llm_response == {"nom": "Toto  ."}
    assert step.job.document.structured_data == {"nom": "Toto"}
    assert step.job.document.analyzed_at == frozen_time
    assert step.job.document.analyze_prompt_tokens_count == 17
    assert step.job.document.analyze_completion_tokens_count == 11


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
    assert step.job.document.analyzed_at is None
    assert step.job.document.analyze_prompt_tokens_count is None
    assert step.job.document.analyze_completion_tokens_count is None


@pytest.mark.django_db
def test_skip_do_not_override_previous_results():
    step = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.CONTENT_ANALYSIS,
        job__batch__target_classifications=["kbis"],
        job__document__classification="devis",
    )
    analyzed_at = datetime(2023, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    llm_response = {"hello": "world"}
    structured_data = {"data": "hello world"}
    step.job.document.llm_response = llm_response
    step.job.document.structured_data = structured_data
    step.job.document.analyzed_at = analyzed_at
    step.job.document.analyze_prompt_tokens_count = 42
    step.job.document.analyze_completion_tokens_count = 43
    step.job.document.save()
    with patch_analyze_content():
        task_analyze_content(step.id)

    step.refresh_from_db()
    assert step.status == ProcessingStatus.SKIPPED
    assert step.error == ""
    assert step.job.document.llm_response == llm_response
    assert step.job.document.structured_data == structured_data
    assert step.job.document.analyzed_at == analyzed_at
    assert step.job.document.analyze_prompt_tokens_count == 42
    assert step.job.document.analyze_completion_tokens_count == 43
