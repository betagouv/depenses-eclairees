from contextlib import contextmanager
from unittest.mock import patch

import pytest

from docia.file_processing.models import ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.pipeline.steps.classification import task_classify_document
from tests.factories.file_processing import ProcessDocumentStepFactory


@contextmanager
def patch_classify():
    with patch("docia.file_processing.processor.classifier.classify_file_with_llm", autospec=True) as m:
        m.return_value = "kbis"
        yield m


@pytest.mark.django_db
def test_task_classification():
    step = ProcessDocumentStepFactory(step_type=ProcessDocumentStepType.CLASSIFICATION)
    with patch_classify():
        task_classify_document(step.id)
    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.classification == "kbis"
    assert step.job.document.classification_type == "llm"
