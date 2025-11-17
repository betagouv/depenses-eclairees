from unittest.mock import patch

import pytest
from celery import states

from docia.file_processing.models import BatchTextExtraction, FileTextExtraction, TaskStatus
from docia.file_processing.text_extraction import extract_text, extract_text_for_folder, get_batch_progress
from docia.tests.factories.data import DataAttachmentFactory


@pytest.mark.django_db
def test_file_text_extraction():
    doc = DataAttachmentFactory()

    with patch("app.processor.extraction_text_from_attachments.process_file") as m:
        m.return_value = ("Hello World", False, 2)
        extract, result = extract_text(doc)

    assert result.status == states.SUCCESS
    extract.refresh_from_db()
    doc.refresh_from_db()
    assert extract.status == TaskStatus.SUCCESS
    assert extract.error == ""
    assert doc.text == "Hello World"
    assert not doc.is_ocr
    assert doc.nb_mot == 2


@pytest.mark.django_db
def test_batch_text_extraction():
    folder = "batch_1234"
    doc1 = DataAttachmentFactory(dossier=folder, filename="doc1.pdf")
    doc2 = DataAttachmentFactory(dossier=folder, filename="doc2.pdf")
    doc_should_not_be_processed = DataAttachmentFactory()

    with patch("app.processor.extraction_text_from_attachments.process_file") as m:
        m.return_value = ("Hello World", False, 2)
        batch, result = extract_text_for_folder(folder)

    assert result.status == states.SUCCESS
    batch.refresh_from_db()
    doc1.refresh_from_db()
    doc2.refresh_from_db()
    doc_should_not_be_processed.refresh_from_db()
    assert batch.status == TaskStatus.SUCCESS
    for doc in [doc1, doc2]:
        assert doc.text == "Hello World"
        assert not doc.is_ocr
        assert doc.nb_mot == 2
    assert doc_should_not_be_processed.text is None
    assert doc_should_not_be_processed.is_ocr is None
    assert doc_should_not_be_processed.nb_mot is None
    extracts = list(batch.filetextextraction_set.order_by("document__filename"))
    for extract in extracts:
        assert extract.status == TaskStatus.SUCCESS
        assert extract.error == ""
    assert len(extracts) == 2


@pytest.mark.django_db
def test_batch_error_handling():
    folder = "batch_1234"
    doc1 = DataAttachmentFactory(dossier=folder, filename="doc1.pdf")
    doc2 = DataAttachmentFactory(dossier=folder, filename="doc2.pdf")

    def process_file(file_path, extension, word_threshold=50):
        if file_path.endswith("doc2.pdf"):
            raise Exception("Error processing doc2")
        return "Hello World", False, 2

    with patch("app.processor.extraction_text_from_attachments.process_file", process_file):
        batch, result = extract_text_for_folder(folder)

    assert result.status == states.SUCCESS
    batch.refresh_from_db()
    doc1.refresh_from_db()
    doc2.refresh_from_db()
    assert batch.status == TaskStatus.FAILURE
    assert doc1.text == "Hello World"
    assert not doc1.is_ocr
    assert doc1.nb_mot == 2
    assert doc2.text is None
    assert doc2.is_ocr is None
    assert doc2.nb_mot is None
    extract1, extract2 = list(batch.filetextextraction_set.order_by("document__filename"))
    assert extract1.status == TaskStatus.SUCCESS
    assert extract1.error == ""
    assert extract2.status == TaskStatus.FAILURE
    assert "Error processing doc2" in extract2.error


@pytest.mark.django_db
def test_get_batch_progress():
    batch = BatchTextExtraction.objects.create(folder="myfolder", status=TaskStatus.STARTED)
    doc1 = DataAttachmentFactory(dossier="myfolder", filename="doc1.pdf")
    doc2 = DataAttachmentFactory(dossier="myfolder", filename="doc2.pdf")
    ext1 = FileTextExtraction.objects.create(batch=batch, document=doc1, status=TaskStatus.PENDING)
    ext2 = FileTextExtraction.objects.create(batch=batch, document=doc2, status=TaskStatus.PENDING)
    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": TaskStatus.STARTED,
        "completed": 0,
        "errors": 0,
        "total": 2,
    }

    # One running
    ext1.status = TaskStatus.STARTED
    ext1.save()

    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": TaskStatus.STARTED,
        "completed": 0,
        "errors": 0,
        "total": 2,
    }

    # One finished
    ext1.status = TaskStatus.SUCCESS
    ext1.save()

    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": TaskStatus.STARTED,
        "completed": 1,
        "errors": 0,
        "total": 2,
    }

    # One failed
    ext1.status = TaskStatus.FAILURE
    ext1.save()

    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": TaskStatus.STARTED,
        "completed": 1,
        "errors": 1,
        "total": 2,
    }

    # Finished
    ext1.status = TaskStatus.FAILURE
    ext1.save()
    ext2.status = TaskStatus.SUCCESS
    ext2.save()
    batch.status = TaskStatus.FAILURE
    batch.save()

    progress = get_batch_progress(batch.id)
    assert progress == {
        "status": TaskStatus.FAILURE,
        "completed": 2,
        "errors": 1,
        "total": 2,
    }
