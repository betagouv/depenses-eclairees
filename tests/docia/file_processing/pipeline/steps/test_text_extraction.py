from contextlib import contextmanager
from unittest.mock import patch

import pytest

from docia.file_processing.models import ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.pipeline.steps.text_extraction import task_extract_text
from docia.file_processing.processor.extraction_text_from_attachments import UnsupportedFileType
from tests.factories.file_processing import ProcessDocumentStepFactory


@contextmanager
def patch_extract_text():
    with patch("docia.file_processing.processor.extraction_text_from_attachments.process_file", autospec=True) as m:
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


@pytest.mark.django_db
def test_skip_unsuported_file_type():
    step = ProcessDocumentStepFactory(step_type=ProcessDocumentStepType.TEXT_EXTRACTION)
    step2 = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.CLASSIFICATION,
        job=step.job,
    )
    with patch_extract_text() as m:
        m.side_effect = UnsupportedFileType("Unsupported file type")
        task_extract_text(step.id)
    step.refresh_from_db()
    assert step.status == ProcessingStatus.SKIPPED
    assert step.error == ""
    assert step.job.document.text is None
    assert step.job.document.is_ocr is None
    assert step.job.document.nb_mot is None

    # next step should be marked as skipped aswell
    step2.refresh_from_db()
    assert step2.status == ProcessingStatus.SKIPPED


@pytest.mark.django_db
def test_empty_text_extracted():
    step = ProcessDocumentStepFactory(step_type=ProcessDocumentStepType.TEXT_EXTRACTION)
    step2 = ProcessDocumentStepFactory(
        step_type=ProcessDocumentStepType.CLASSIFICATION,
        job=step.job,
    )
    with patch_extract_text() as m:
        m.return_value = ("", False, 0)
        task_extract_text(step.id)
    step.refresh_from_db()
    assert step.status == ProcessingStatus.FAILURE
    assert step.error == f"Failed to extract text - empty result - {step.job.document.file.name}"
    assert step.job.document.text is None
    assert step.job.document.is_ocr is None
    assert step.job.document.nb_mot is None

    # next step should be marked as skipped
    step2.refresh_from_db()
    assert step2.status == ProcessingStatus.SKIPPED
