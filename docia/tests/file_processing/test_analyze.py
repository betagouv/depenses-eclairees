from unittest.mock import patch

import pytest
from celery import states

import pandas as pd

from docia.file_processing.analyze import analyze_document, analyze_documents_in_folder
from docia.file_processing.models import JobName, JobStatus
from docia.tests.factories.data import DataAttachmentFactory


@pytest.mark.django_db
def test_document_analyze():
    doc = DataAttachmentFactory()

    with patch("app.processor.analyze_content.analyze_file_text", autospec=True) as m:
        m.return_value = {
            "llm_response": {"nom": "Toto"},
            "json_error": None,
        }
        job, result = analyze_document(doc)

    assert result.status == states.SUCCESS
    assert job.celery_task_id == result.task_id
    assert job.job_name == JobName.ANALYZE
    job.refresh_from_db()
    doc.refresh_from_db()
    assert job.status == JobStatus.SUCCESS
    assert job.error == ""
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.duration is not None
    assert doc.llm_response == {"nom": "Toto"}
    assert doc.json_error is None


@pytest.mark.django_db
def test_batch_analyze():
    folder = "batch_1234"
    doc1 = DataAttachmentFactory(dossier=folder, filename="doc1.pdf")
    doc2 = DataAttachmentFactory(dossier=folder, filename="doc2.pdf")
    doc_should_not_be_processed = DataAttachmentFactory()

    with patch("app.processor.analyze_content.analyze_file_text", autospec=True) as m:
        m.return_value = {
            "llm_response": {"nom": "Toto"},
            "json_error": None,
        }
        batch, result = analyze_documents_in_folder(folder)

    assert result.status == states.SUCCESS
    assert batch.celery_task_id == result.task_id
    assert batch.job_name == JobName.ANALYZE
    batch.refresh_from_db()
    doc1.refresh_from_db()
    doc2.refresh_from_db()
    doc_should_not_be_processed.refresh_from_db()
    assert batch.status == JobStatus.SUCCESS
    for doc in [doc1, doc2]:
        assert doc.llm_response == {"nom": "Toto"}
        assert doc.json_error is None
    assert doc_should_not_be_processed.llm_response is None
    assert doc_should_not_be_processed.json_error is None
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

    def analyze_file_text(
        filename: str,
        text: str,
        df_attributes: pd.DataFrame,
        classification: str,
        llm_model: str = 'albert-large',
        temperature: float = 0.0,
    ):
        if filename.endswith("doc2.pdf"):
            raise Exception("Error processing doc2")
        return {
            "llm_response": {"nom": "Toto"},
            "json_error": None,
        }

    with patch("app.processor.analyze_content.analyze_file_text", autospec=True) as m:
        m.side_effect = analyze_file_text
        batch, result = analyze_documents_in_folder(folder)

    assert result.status == states.SUCCESS
    batch.refresh_from_db()
    doc1.refresh_from_db()
    doc2.refresh_from_db()
    assert batch.status == JobStatus.FAILURE
    assert doc1.llm_response == {"nom": "Toto"}
    assert doc1.json_error is None
    assert doc2.llm_response is None
    assert doc2.json_error is None
    job1, job2 = list(batch.documentjob_set.order_by("document__filename"))
    assert job1.status == JobStatus.SUCCESS
    assert job1.error == ""
    assert job2.status == JobStatus.FAILURE
    assert "Error processing doc2" in job2.error
    assert "Exception: Error processing doc2" in job2.traceback
    assert "Traceback" in job2.traceback
