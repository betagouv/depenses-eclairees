from contextlib import contextmanager
from unittest import mock
from unittest.mock import patch

import pytest

from docia.file_processing.models import ProcessDocumentStep, ProcessDocumentStepType, ProcessingStatus
from docia.file_processing.pipeline import close_and_retry_stuck_batches, launch_batch, retry_batch_failures
from docia.models import DataAttachment
from docia.tests.factories.data import DataAttachmentFactory
from docia.tests.factories.file_processing import (
    ProcessDocumentBatchFactory,
    ProcessDocumentJobFactory,
    ProcessDocumentStepFactory,
)


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
        steps = list(job.step_set.order_by("order"))
        for step in steps:
            assert step.status == ProcessingStatus.SUCCESS
            assert step.error == ""
        expected_steps = [
            (1, ProcessDocumentStepType.TEXT_EXTRACTION),
            (2, ProcessDocumentStepType.CLASSIFICATION),
            (3, ProcessDocumentStepType.INFO_EXTRACTION),
        ]
        actual_step_types = [(step.order, step.step_type) for step in steps]
        assert actual_step_types == expected_steps


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


@pytest.mark.django_db
def test_retry_batch():
    batch = ProcessDocumentBatchFactory(status=ProcessingStatus.FAILURE)
    # Jobs to retry (status=failure)
    retry_job_1 = ProcessDocumentJobFactory(
        batch=batch, status=ProcessingStatus.FAILURE, document__dossier=batch.folder
    )
    retry_job_2 = ProcessDocumentJobFactory(
        batch=batch, status=ProcessingStatus.FAILURE, document__dossier=batch.folder
    )
    # Job not to retry (status!=failure)
    ProcessDocumentJobFactory(batch=batch, status=ProcessingStatus.PENDING, document__dossier=batch.folder)
    ProcessDocumentJobFactory(batch=batch, status=ProcessingStatus.STARTED, document__dossier=batch.folder)
    ProcessDocumentJobFactory(batch=batch, status=ProcessingStatus.SUCCESS, document__dossier=batch.folder)
    ProcessDocumentJobFactory(batch=batch, status=ProcessingStatus.CANCELLED, document__dossier=batch.folder)

    with patch_extract_text(), patch_classify(), patch_extract_info():
        new_batch, _result = retry_batch_failures(batch.id)

    job1, job2 = new_batch.job_set.order_by("document__filename")
    assert [job1.document, job2.document] == [retry_job_1.document, retry_job_2.document]


@pytest.mark.django_db
def test_retry_batch_with_cancelled():
    batch = ProcessDocumentBatchFactory(status=ProcessingStatus.FAILURE)
    # Jobs to retry (status=failure|cancelled)
    retry_job_1 = ProcessDocumentJobFactory(
        batch=batch, status=ProcessingStatus.FAILURE, document__dossier=batch.folder
    )
    retry_job_2 = ProcessDocumentJobFactory(
        batch=batch, status=ProcessingStatus.CANCELLED, document__dossier=batch.folder
    )
    # Job not to retry (status=success)
    ProcessDocumentJobFactory(batch=batch, status=ProcessingStatus.SUCCESS, document__dossier=batch.folder)

    with patch_extract_text(), patch_classify(), patch_extract_info():
        new_batch, _result = retry_batch_failures(batch.id, retry_cancelled=True)

    new_batch.refresh_from_db()
    assert new_batch.retry_of == batch
    assert new_batch.folder == batch.folder
    assert new_batch.target_classifications == batch.target_classifications

    job1, job2 = new_batch.job_set.order_by("document__filename")
    assert [job1.document, job2.document] == [retry_job_1.document, retry_job_2.document]


@pytest.mark.django_db
def test_close_and_retry_stuck_batches():
    batch = ProcessDocumentBatchFactory(status=ProcessingStatus.STARTED)
    ProcessDocumentStepFactory(job__batch=batch, finished_at="2024-01-01")
    with (
        patch("docia.file_processing.pipeline.retry_batch_failures", autospec=True) as m_retry,
        patch("docia.file_processing.pipeline.cancel_batch", autospec=True) as m_cancel,
    ):
        new_batch = ProcessDocumentBatchFactory()
        m_retry.return_value = (new_batch, mock.Mock())

        r = close_and_retry_stuck_batches()

        m_cancel.assert_called_once_with(batch.id)
        m_retry.assert_called_once_with(batch.id, retry_cancelled=True)

        assert r == [(batch.id, new_batch.id)]
