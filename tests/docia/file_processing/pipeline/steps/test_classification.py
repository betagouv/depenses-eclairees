from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

import freezegun
import pytest

from docia.file_processing.llm.client import LLMUsage
from docia.file_processing.models import ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.pipeline.steps.classification import task_classify_document
from docia.file_processing.processor.classifier import ClassifyResult
from docia.file_processing.processor.constants import DEFAULT_CLASSIFICATION_MODEL
from tests.factories.file_processing import ProcessDocumentStepFactory


@contextmanager
def patch_classify():
    with patch("docia.file_processing.processor.classifier.classify_file_with_llm", autospec=True) as m:
        m.return_value = ClassifyResult(
            classification="kbis",
            model=DEFAULT_CLASSIFICATION_MODEL,
            usage=LLMUsage(prompt_tokens=23, completion_tokens=3),
        )
        yield m


@pytest.mark.django_db
def test_task_classification():
    step = ProcessDocumentStepFactory(step_type=ProcessDocumentStepType.CLASSIFICATION)
    last_updated_at = step.job.document.updated_at
    frozen_time = last_updated_at + timedelta(days=30)
    with freezegun.freeze_time(frozen_time):
        with patch_classify():
            task_classify_document(step.id)
    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.classification == "kbis"
    assert step.job.document.classification_type == "llm"
    assert step.job.document.classified_at == frozen_time
    assert step.job.document.classification_prompt_tokens_count == 23
    assert step.job.document.classification_completion_tokens_count == 3
    assert step.job.document.classification_model == DEFAULT_CLASSIFICATION_MODEL
    assert step.job.document.updated_at == frozen_time
