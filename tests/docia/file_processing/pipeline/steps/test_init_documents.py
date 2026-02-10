from unittest import mock
from unittest.mock import patch

import pytest

from docia.file_processing.models import FileInfo
from docia.file_processing.pipeline.steps.init_documents import (
    bulk_create_attachments,
    bulk_create_batches,
    bulk_create_engagements,
    bulk_create_links_document_engagement,
    get_files_info,
    init_documents_in_folder,
    listdir_chunk,
)
from docia.models import DataBatch, DataEngagement, Document
from tests.factories.data import DataBatchFactory, DataEngagementFactory, DocumentFactory
from tests.factories.file_processing import FileInfoFactory


@pytest.mark.django_db
def test_init_documents_in_folder():
    with (
        patch("django.core.files.storage.default_storage.listdir", autospec=True) as m_listdir,
        patch("docia.file_processing.pipeline.steps.init_documents.get_files_info", autospec=True) as m_get_files_info,
    ):
        m_listdir.return_value = ([], ["doc1.pdf", "doc2.pdf"])
        file_info_1 = FileInfoFactory(filename="doc1.pdf", num_ej="ej1")
        file_info_2 = FileInfoFactory(filename="doc2.pdf", num_ej="ej1")
        m_get_files_info.return_value = [file_info_1, file_info_2]
        init_documents_in_folder("folder", "batch1")
        m_listdir.assert_called_once_with("folder")

        ej = DataEngagement.objects.get(num_ej="ej1")
        data_batch = DataBatch.objects.get(batch="batch1")
        assert data_batch.ej.id == ej.id


@pytest.mark.parametrize(
    "number_of_files,chunks,chunk_size",
    [
        (48, 5, 10),
        (435, 5, 100),
    ],
)
@pytest.mark.django_db
def test_init_documents_in_folder_chunking(number_of_files, chunks, chunk_size):
    with (
        patch("django.core.files.storage.default_storage.listdir", autospec=True) as m_listdir,
        patch("docia.file_processing.pipeline.steps.init_documents.get_files_info", autospec=True) as m_get_files_info,
    ):
        m_listdir.return_value = ([], [f"doc{i}.pdf" for i in range(1, number_of_files)])
        m_get_files_info.return_value = []
        init_documents_in_folder("folder", "batch1")
        m_listdir.assert_called_once_with("folder")
        expected_calls = [mock.call("folder", chunk_number=i, chunk_size=chunk_size) for i in range(chunks)]
        m_get_files_info.assert_has_calls(expected_calls)
        assert len(m_get_files_info.mock_calls) == len(expected_calls)


@pytest.mark.django_db
def test_get_files_info():
    gen_data_infos = []

    def mock_get_file_initial_info(filename: str, directory_path: str):
        i = FileInfoFactory.build(filename=filename, folder=directory_path)
        data = {
            "filename": i.filename,
            "num_EJ": i.num_ej,
            "dossier": i.folder,
            "extension": i.extension,
            "date_creation": i.created_date,
            "taille": i.size,
            "hash": i.hash,
        }
        gen_data_infos.append(data)
        return data

    def assert_files_info(files_info):
        assert len(files_info) == 2
        assert files_info[0].filename == "doc1.pdf"
        assert files_info[0].num_ej == gen_data_infos[0]["num_EJ"]
        assert files_info[0].folder == gen_data_infos[0]["dossier"]
        assert files_info[0].file.name == "folder/doc1.pdf"
        assert files_info[0].extension == gen_data_infos[0]["extension"]
        assert files_info[0].created_date == gen_data_infos[0]["date_creation"]
        assert files_info[0].size == gen_data_infos[0]["taille"]
        assert files_info[0].hash == gen_data_infos[0]["hash"]
        assert files_info[1].filename == "doc2.pdf"
        assert files_info[1].num_ej == gen_data_infos[1]["num_EJ"]
        assert files_info[1].folder == gen_data_infos[1]["dossier"]
        assert files_info[1].file.name == "folder/doc2.pdf"
        assert files_info[1].extension == gen_data_infos[1]["extension"]
        assert files_info[1].created_date == gen_data_infos[1]["date_creation"]
        assert files_info[1].size == gen_data_infos[1]["taille"]
        assert files_info[1].hash == gen_data_infos[1]["hash"]

    with (
        patch("app.file_manager.cleaner.get_file_initial_info", autospec=True) as m_get_file_info,
        patch("docia.file_processing.pipeline.steps.init_documents.listdir_chunk", autospec=True) as m_listdir,
    ):
        m_get_file_info.side_effect = mock_get_file_initial_info
        m_listdir.return_value = ["doc1.pdf", "doc2.pdf"]
        files_info = get_files_info("folder", 1, 10)
        assert_files_info(files_info)
        files_info = FileInfo.objects.order_by("filename")
        assert_files_info(files_info)

        # Now they should be in cache, no call to get_file_info
        expected_nb_calls = m_get_file_info.call_count
        files_info = get_files_info("folder", 1, 10)
        assert_files_info(files_info)
        files_info = FileInfo.objects.order_by("filename")
        assert_files_info(files_info)
        assert m_get_file_info.call_count == expected_nb_calls


def test_listdir_chunk():
    with patch("django.core.files.storage.default_storage.listdir", autospec=True) as m:
        # files can be in any order
        filenames = [f"doc{i:0>3}.pdf" for i in range(100, 0, -1)]
        m.return_value = ([], filenames)

        # Get first items
        assert listdir_chunk("folder", 0, 3) == ["doc001.pdf", "doc002.pdf", "doc003.pdf"]

        # Get items in the middle
        assert listdir_chunk("folder", 2, 3) == ["doc007.pdf", "doc008.pdf", "doc009.pdf"]

        # Get items out of bound
        assert listdir_chunk("folder", 100, 3) == []


@pytest.mark.django_db
def test_bulk_create_engagements():
    num_ejs = ["EJ1", "EJ2", "EJ3"]
    bulk_create_engagements(num_ejs)
    engagements = list(DataEngagement.objects.all().order_by("num_ej").values_list("num_ej", flat=True))
    assert engagements == num_ejs


@pytest.mark.django_db
def test_bulk_create_engagements_ignore_duplicates():
    ej = DataEngagementFactory(num_ej="EJ1", designation="toto")
    bulk_create_engagements(["EJ1"])
    ej.refresh_from_db()
    engagements = list(DataEngagement.objects.all().order_by("num_ej").values("id", "num_ej", "designation"))
    assert engagements == [{"id": ej.id, "num_ej": "EJ1", "designation": "toto"}]


@pytest.mark.django_db
def test_bulk_create_batches():
    ej1, ej2, ej3 = DataEngagementFactory.create_batch(3)
    num_ejs = [ej1.num_ej, ej2.num_ej, ej3.num_ej]
    bulk_create_batches(num_ejs, "Batch")
    batches = list(DataBatch.objects.all().order_by("batch").values("batch", "ej"))
    assert batches == [
        {"batch": "Batch", "ej": ej1.num_ej},
        {"batch": "Batch", "ej": ej2.num_ej},
        {"batch": "Batch", "ej": ej3.num_ej},
    ]


@pytest.mark.django_db
def test_bulk_create_batches_ignore_duplicates():
    ej = DataEngagementFactory()
    batch = DataBatchFactory(batch="Batch", ej=ej)
    bulk_create_batches([ej.num_ej], batch.batch)
    batches = list(DataBatch.objects.all().order_by("batch").values("batch", "ej"))
    assert batches == [
        {"batch": "Batch", "ej": ej.num_ej},
    ]


def assert_documents_equals_files_info(qs_documents, files_info):
    values = list(qs_documents.order_by("file").values("filename", "extension", "dossier", "taille", "hash", "file"))
    sorted_files_info = sorted(files_info, key=lambda x: x.file.name)
    expected = [
        {
            "filename": file_info.filename,
            "extension": file_info.extension,
            "dossier": file_info.folder,
            "taille": file_info.size,
            "hash": file_info.hash,
            "file": file_info.file.name,
        }
        for file_info in sorted_files_info
    ]
    assert values == expected


@pytest.mark.django_db
def test_bulk_create_attachments():
    files_info = FileInfoFactory.create_batch(3)
    bulk_create_attachments(files_info)
    assert_documents_equals_files_info(Document.objects.all(), files_info)


@pytest.mark.django_db
def test_bulk_create_attachments_ignore_duplicates():
    file_info = FileInfoFactory()
    # Run the bulk_create twice
    bulk_create_attachments([file_info])
    bulk_create_attachments([file_info])
    # Assert only one inserted
    assert_documents_equals_files_info(Document.objects.all(), [file_info])


@pytest.mark.django_db
def test_bulk_create_links_doc_engagement():
    files_info = FileInfoFactory.create_batch(3)
    for fi in files_info:
        DataEngagementFactory(num_ej=fi.num_ej)
        DocumentFactory(file=fi.file)
    bulk_create_links_document_engagement(files_info)
    RelModel = Document.engagements.through
    links = list(RelModel.objects.order_by("document__file").values("document__file", "dataengagement__num_ej"))
    assert links == [{"document__file": fi.file.name, "dataengagement__num_ej": fi.num_ej} for fi in files_info]


@pytest.mark.django_db
def test_bulk_create_links_doc_engagement_ignores_duplicates():
    file_info = FileInfoFactory()
    ej = DataEngagementFactory(num_ej=file_info.num_ej)
    doc = DocumentFactory(file=file_info.file)
    doc.engagements.add(ej)
    bulk_create_links_document_engagement([file_info])
    RelModel = Document.engagements.through
    links = list(RelModel.objects.order_by("document__file").values("document__file", "dataengagement__num_ej"))
    assert links == [{"document__file": doc.file.name, "dataengagement__num_ej": ej.num_ej}]
