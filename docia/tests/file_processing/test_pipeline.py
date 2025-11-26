from contextlib import contextmanager
from unittest.mock import patch

import pytest

from docia.file_processing.models import ProcessDocumentStep, ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.pipeline import launch_batch
from docia.models import DataAttachment
from docia.tests.factories.data import DataAttachmentFactory


@contextmanager
def patch_extract_text():
    with patch("docia.file_processing.text_extraction.ExtractTextStepRunner.process", autospec=True) as m:
        yield m


@contextmanager
def patch_classify():
    with patch("docia.file_processing.classification.ClassifyStepRunner.process", autospec=True) as m:
        yield m


@contextmanager
def patch_extract_info():
    with patch("docia.file_processing.info_extraction.ExtractInfoStepRunner.process", autospec=True) as m:
        yield m


@pytest.mark.django_db
def test_batch():
    folder = "batch_1234"
    doc1 = DataAttachmentFactory(dossier=folder, filename="doc1.pdf")
    doc2 = DataAttachmentFactory(dossier=folder, filename="doc2.pdf")
    _doc_should_not_be_processed = DataAttachmentFactory()

    with patch_extract_text() as m_text, patch_classify() as m_classify, patch_extract_info() as m_info:
        batch, result = launch_batch(folder=folder)

    assert result.ready()
    assert batch.celery_task_id == result.id
    batch.refresh_from_db()
    assert [job.document for job in batch.job_set.order_by("document__filename")] == [doc1, doc2]
    assert m_text.call_count == 2
    assert m_classify.call_count == 2
    assert m_info.call_count == 2
    assert batch.status == ProcessingStatus.SUCCESS
    jobs = list(batch.job_set.order_by("document__filename"))
    for job in jobs:
        assert job.status == ProcessingStatus.SUCCESS
        steps = list(job.step_set.all())
        for step in steps:
            assert step.status == ProcessingStatus.SUCCESS
            assert step.error == ""
        expected_step_types = [
            ProcessDocumentStepType.TEXT_EXTRACTION,
            ProcessDocumentStepType.CLASSIFICATION,
            ProcessDocumentStepType.INFO_EXTRACTION,
        ]
        actual_step_types = [step.step_type for step in steps]
        assert actual_step_types == expected_step_types


@pytest.mark.django_db
def test_batch_error_handling():
    folder = "batch_1234"
    DataAttachmentFactory(dossier=folder, filename="doc1.pdf", text="")
    DataAttachmentFactory(dossier=folder, filename="doc2.pdf")

    def mock_extract_text(self, step: ProcessDocumentStep):
        if step.job.document.filename == "doc2.pdf":
            raise Exception("Error processing doc2")

    with patch_extract_text() as m_text, patch_classify() as m_classify, patch_extract_info() as m_info:
        m_text.side_effect = mock_extract_text
        batch, result = launch_batch(folder=folder)

    assert result.ready()
    batch.refresh_from_db()
    assert batch.status == ProcessingStatus.FAILURE
    assert m_text.call_count == 2
    assert m_classify.call_count == 1
    assert m_info.call_count == 1
    job1, job2 = list(batch.job_set.order_by("document__filename"))

    # All steps in job1 should be success
    for step in job1.step_set.all():
        assert step.status == ProcessingStatus.SUCCESS
        assert step.error == ""

    # Step text extract in job2 should be failure, others should be skipped
    failed_step = job2.step_set.get(step_type=ProcessDocumentStepType.TEXT_EXTRACTION)
    assert failed_step.status == ProcessingStatus.FAILURE
    assert "Error processing doc2" in failed_step.error
    assert "Exception: Error processing doc2" in failed_step.traceback
    assert "Traceback" in failed_step.traceback
    # Other steps should be skipped
    for step in job2.step_set.exclude(step_type=ProcessDocumentStepType.TEXT_EXTRACTION):
        assert step.status == ProcessingStatus.SKIPPED
        assert step.error == ""


@pytest.mark.django_db
def test_launch_batch_filter_documents_by_classifications_and_folder():
    folder = "batch_1234"
    DataAttachmentFactory(dossier=folder, filename="doc1.pdf")
    DataAttachmentFactory(dossier=folder, filename="doc2.pdf")
    _doc_should_not_be_processed = DataAttachmentFactory(dossier=folder)

    with patch_extract_text(), patch_classify(), patch_extract_info():
        batch, _result = launch_batch(folder=folder, target_classifications=["kbis", "devis"])

    batch.refresh_from_db()
    assert batch.target_classifications == ["kbis", "devis"]


@pytest.mark.django_db
def test_launch_batch_specify_qs():
    folder = "batch_1234"
    doc1 = DataAttachmentFactory(dossier=folder, filename="doc1.pdf")
    doc2 = DataAttachmentFactory(dossier=folder, filename="doc2.pdf")
    _doc_should_not_be_processed = DataAttachmentFactory(dossier=folder)

    qs = DataAttachment.objects.filter(id__in=(doc1.id, doc2.id))
    with patch_extract_text(), patch_classify(), patch_extract_info():
        batch, _result = launch_batch(qs_documents=qs)

    batch.refresh_from_db()
    job1, job2 = batch.job_set.order_by("document__filename")
    assert [doc1, doc2] == [job1.document, job2.document]
