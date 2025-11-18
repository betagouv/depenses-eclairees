from unittest.mock import patch

import pytest
from celery import states

from docia.file_processing.classification import classify_document, classify_documents_in_folder
from docia.file_processing.models import JobName, JobStatus
from docia.tests.factories.data import DataAttachmentFactory


@pytest.mark.django_db
def test_document_classification():
    doc = DataAttachmentFactory()

    with patch("app.file_manager.classifier.classify_file_with_llm", autospec=True) as m:
        m.return_value = "kbis"
        job, result = classify_document(doc)

    assert result.status == states.SUCCESS
    assert job.celery_task_id == result.task_id
    assert job.job_name == JobName.CLASSIFICATION
    job.refresh_from_db()
    doc.refresh_from_db()
    assert job.status == JobStatus.SUCCESS
    assert job.error == ""
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.duration is not None
    assert doc.classification == "kbis"
    assert doc.classification_type == "llm"


@pytest.mark.django_db
def test_batch_classification():
    folder = "batch_1234"
    doc1 = DataAttachmentFactory(dossier=folder, filename="doc1.pdf")
    doc2 = DataAttachmentFactory(dossier=folder, filename="doc2.pdf")
    doc_should_not_be_processed = DataAttachmentFactory()

    with patch("app.file_manager.classifier.classify_file_with_llm", autospec=True) as m:
        m.return_value = "kbis"
        batch, result = classify_documents_in_folder(folder)

    assert result.status == states.SUCCESS
    assert batch.celery_task_id == result.task_id
    assert batch.job_name == JobName.CLASSIFICATION
    batch.refresh_from_db()
    doc1.refresh_from_db()
    doc2.refresh_from_db()
    doc_should_not_be_processed.refresh_from_db()
    assert batch.status == JobStatus.SUCCESS
    for doc in [doc1, doc2]:
        assert doc.classification == "kbis"
        assert doc.classification_type == "llm"
    assert doc_should_not_be_processed.classification is None
    assert doc_should_not_be_processed.classification_type is None
    jobs = list(batch.documentjob_set.order_by("document__filename"))
    for job in jobs:
        assert job.status == JobStatus.SUCCESS
        assert job.error == ""
    assert len(jobs) == 2


@pytest.mark.django_db
def test_batch_error_handling():
    folder = "batch_1234"
    doc1 = DataAttachmentFactory(dossier=folder, filename="doc1.pdf", text="")
    doc2 = DataAttachmentFactory(dossier=folder, filename="doc2.pdf")

    def classify_file_with_llm(
        filename: str,
        text: str,
        list_classification: dict,
        llm_model: str = "albert-large",
    ):
        if filename.endswith("doc2.pdf"):
            raise Exception("Error processing doc2")
        return "kbis"

    with patch("app.file_manager.classifier.classify_file_with_llm", autospec=True) as m:
        m.side_effect = classify_file_with_llm
        batch, result = classify_documents_in_folder(folder)

    assert result.status == states.SUCCESS
    batch.refresh_from_db()
    doc1.refresh_from_db()
    doc2.refresh_from_db()
    assert batch.status == JobStatus.FAILURE
    assert doc1.classification == "kbis"
    assert doc1.classification_type == "llm"
    assert doc2.classification is None
    assert doc2.classification_type is None
    job1, job2 = list(batch.documentjob_set.order_by("document__filename"))
    assert job1.status == JobStatus.SUCCESS
    assert job1.error == ""
    assert job2.status == JobStatus.FAILURE
    assert "Error processing doc2" in job2.error
    assert "Exception: Error processing doc2" in job2.traceback
    assert "Traceback" in job2.traceback
