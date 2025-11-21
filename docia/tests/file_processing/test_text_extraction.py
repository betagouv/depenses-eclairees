from contextlib import contextmanager
from unittest.mock import patch

import pytest

from docia.file_processing.models import ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.text_extraction import task_extract_text
from docia.tests.factories.file_processing import ProcessDocumentStepFactory


@contextmanager
def patch_extract_text():
    with patch("app.processor.extraction_text_from_attachments.process_file", autospec=True) as m:
        m.return_value = ("Hello World", False, 2)
        yield m


@pytest.mark.django_db
def test_task_extract_info():
    step = ProcessDocumentStepFactory(step_type=ProcessDocumentStepType.TEXT_EXTRACTION)
    with patch_extract_text():
        task_extract_text(step.id)
    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS
    assert step.error == ""
    assert step.job.document.text == "Hello World"
    assert not step.job.document.is_ocr
    assert step.job.document.nb_mot == 2
