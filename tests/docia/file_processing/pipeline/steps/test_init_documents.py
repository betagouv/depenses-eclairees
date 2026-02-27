from unittest import mock
from unittest.mock import patch

import pytest

from docia.file_processing.models import ExternalLinkDocumentOrder, FileInfo
from docia.file_processing.pipeline.steps.init_documents import (
    bulk_create_batches,
    bulk_create_documents,
    bulk_create_engagements,
    bulk_create_links_document_engagement_using_external_data,
    bulk_create_links_document_engagement_using_filenames,
    get_files_info,
    init_documents_from_external_filter_by_num_ejs,
    init_documents_in_folder,
    listdir_chunk,
    remove_duplicates,
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
        num_ej1 = "1234567890"
        num_ej2 = "2234567890"
        m_listdir.return_value = ([], [f"{num_ej1}_doc1.pdf", f"{num_ej2}_doc2.pdf"])
        file_info_1 = FileInfoFactory(external_id=None, filename=f"{num_ej1}_doc1.pdf", folder="folder")
        file_info_2 = FileInfoFactory(external_id=None, filename=f"{num_ej2}_doc2.pdf", folder="folder")
        m_get_files_info.return_value = [file_info_1, file_info_2]
        init_documents_in_folder("folder", "batch1")
        m_listdir.assert_called_once_with("folder")

        batches = list(DataBatch.objects.values("ej__num_ej", "batch"))
        assert batches == [
            {"ej__num_ej": num_ej1, "batch": "batch1"},
            {"ej__num_ej": num_ej2, "batch": "batch1"},
        ]

        documents = list(
            Document.objects.order_by("file").values("file", "extension", "hash", "taille", "engagements__num_ej")
        )
        assert documents == [
            {
                "file": f"folder/{file_info_1.filename}",
                "extension": "pdf",
                "hash": file_info_1.hash,
                "taille": file_info_1.size,
                "engagements__num_ej": num_ej1,
            },
            {
                "file": f"folder/{file_info_2.filename}",
                "extension": "pdf",
                "hash": file_info_2.hash,
                "taille": file_info_2.size,
                "engagements__num_ej": num_ej2,
            },
        ]


@pytest.mark.django_db
def test_init_documents_in_folder_complex_case():
    """Case with duplicates"""
    with (
        patch("django.core.files.storage.default_storage.listdir", autospec=True) as m_listdir,
        patch("docia.file_processing.pipeline.steps.init_documents.get_files_info", autospec=True) as m_get_files_info,
    ):
        num_ej1 = "1234567890"
        num_ej2 = "2234567890"
        m_listdir.return_value = ([], [f"{num_ej1}_doc1.pdf", f"{num_ej2}_doc2.pdf"])
        file_info_1 = FileInfoFactory(external_id=None, filename=f"{num_ej1}_doc1.pdf", folder="folder")
        file_info_2 = FileInfoFactory(external_id=None, filename=f"{num_ej2}_doc2.pdf", folder="folder")
        # Duplicate handling (on FileInfo)
        file_info_2_dup = FileInfoFactory(
            external_id=None, hash=file_info_2.hash, filename=f"{num_ej2}_doc2_2.pdf", folder="folder"
        )
        # Duplicate handling (on Document)
        file_info_3 = FileInfoFactory(external_id=None, filename=f"{num_ej2}_doc3.pdf", folder="folder")
        existing_doc = DocumentFactory(hash=file_info_3.hash, taille=42)

        m_get_files_info.return_value = [file_info_1, file_info_2, file_info_2_dup, file_info_3]
        init_documents_in_folder("folder", "batch1")
        m_listdir.assert_called_once_with("folder")

        batches = list(DataBatch.objects.values("ej__num_ej", "batch"))
        assert batches == [
            {"ej__num_ej": num_ej1, "batch": "batch1"},
            {"ej__num_ej": num_ej2, "batch": "batch1"},
        ]

        documents = list(
            Document.objects.order_by("file").values("file", "extension", "hash", "taille", "engagements__num_ej")
        )
        assert documents == [
            {
                "file": f"folder/{file_info_1.filename}",
                "extension": "pdf",
                "hash": file_info_1.hash,
                "taille": file_info_1.size,
                "engagements__num_ej": num_ej1,
            },
            {
                "file": f"folder/{file_info_2.filename}",
                "extension": "pdf",
                "hash": file_info_2.hash,
                "taille": file_info_2.size,
                "engagements__num_ej": num_ej2,
            },
            {
                "engagements__num_ej": num_ej2,
                "extension": "txt",
                "file": existing_doc.file.name,
                "hash": existing_doc.hash,
                "taille": 42,
            },
        ]


@pytest.mark.django_db
def test_init_documents_in_folder_handle_duplicate_file_info():
    """Test with duplicate file infos during init_documents process.

    Only one Document should be created, but relationships with
    Engagements (Batch<>Engagement and Document<>Engagement) should still be created.
    """
    with (
        patch("django.core.files.storage.default_storage.listdir", autospec=True) as m_listdir,
        patch("docia.file_processing.pipeline.steps.init_documents.get_files_info", autospec=True) as m_get_files_info,
    ):
        num_ej1 = "1234567890"
        num_ej2 = "2234567890"
        file_info_1 = FileInfoFactory(external_id=None, filename=f"{num_ej1}_doc1.pdf", folder="folder")
        # Duplicate FileInfo
        file_info_2 = FileInfoFactory(
            external_id=None, hash=file_info_1.hash, filename=f"{num_ej2}_doc1.pdf", folder="folder"
        )

        # Set mock returns
        m_listdir.return_value = ([], [file_info_1.filename, file_info_2.filename])
        m_get_files_info.return_value = [file_info_1, file_info_2]

        # Call init
        init_documents_in_folder("folder", "batch1")

        # Assert: Only one document inserted
        assert Document.objects.count() == 1

        # Assert: Even if duplicates, all relations with Engagement should be inserted
        batches = list(DataBatch.objects.values("ej__num_ej", "batch"))
        assert batches == [
            {"ej__num_ej": num_ej1, "batch": "batch1"},
            {"ej__num_ej": num_ej2, "batch": "batch1"},
        ]

        # Assert: Even if duplicates, all relations with Engagement should be inserted
        documents = list(Document.objects.order_by("engagements__num_ej").values("hash", "engagements__num_ej", "file"))
        assert documents == [
            {
                "engagements__num_ej": num_ej1,
                "hash": file_info_1.hash,
                "file": file_info_1.file,
            },
            {
                "engagements__num_ej": num_ej2,
                "hash": file_info_1.hash,
                "file": file_info_1.file,
            },
        ]


@pytest.mark.django_db
def test_init_documents_in_folder_handle_duplicate_document():
    """Test with an existing Document (same hash) during init_documents process.

    No Document should be created, but relationships with Engagements (Batch<>Engagement
    and Document<>Engagement) should still be created. Previous relationships should
    be preserved.
    """
    with (
        patch("django.core.files.storage.default_storage.listdir", autospec=True) as m_listdir,
        patch("docia.file_processing.pipeline.steps.init_documents.get_files_info", autospec=True) as m_get_files_info,
    ):
        num_ej1 = "1234567890"
        num_ej2 = "2234567890"
        file_info_1 = FileInfoFactory(external_id=None, filename=f"{num_ej1}_doc1.pdf", folder="folder")
        # Existing Document
        existing_doc = DocumentFactory(filename="existing_doc.pdf", hash=file_info_1.hash, taille=42)
        existing_doc.engagements.add(DataEngagementFactory(num_ej=num_ej2))

        # Mock
        m_listdir.return_value = ([], [file_info_1.filename])
        m_get_files_info.return_value = [file_info_1]

        # Call init
        init_documents_in_folder("folder", "batch1")

        # Assert: No Document inserted
        assert Document.objects.count() == 1

        # Assert: New rel with Batch should be created
        batches = list(DataBatch.objects.values("ej__num_ej", "batch").order_by("ej__num_ej"))
        assert batches == [
            {"ej__num_ej": num_ej1, "batch": "batch1"},
        ]

        # Assert: Previous rel should be kept, new one should be created
        documents = list(Document.objects.order_by("engagements__num_ej").values("file", "hash", "engagements__num_ej"))
        assert documents == [
            {
                "engagements__num_ej": num_ej1,
                "file": existing_doc.file.name,
                "hash": existing_doc.hash,
            },
            {
                "engagements__num_ej": num_ej2,
                "file": existing_doc.file.name,
                "hash": existing_doc.hash,
            },
        ]


@pytest.mark.django_db
def test_init_documents_from_external():
    file_info_1, file_info_2 = FileInfoFactory.create_batch(2)
    num_ej1 = "1234567890"
    num_ej2 = "2234567890"
    ExternalLinkDocumentOrder.objects.create(document_external_id=file_info_1.external_id, order_external_id=num_ej1)
    ExternalLinkDocumentOrder.objects.create(document_external_id=file_info_2.external_id, order_external_id=num_ej2)

    init_documents_from_external_filter_by_num_ejs([num_ej1, num_ej2], "batch1")

    batches = list(DataBatch.objects.values("ej__num_ej", "batch"))
    assert batches == [
        {"ej__num_ej": num_ej1, "batch": "batch1"},
        {"ej__num_ej": num_ej2, "batch": "batch1"},
    ]

    documents = list(
        Document.objects.order_by("file").values("file", "extension", "hash", "taille", "engagements__num_ej")
    )
    assert documents == [
        {
            "file": file_info_1.file.name,
            "extension": "pdf",
            "hash": file_info_1.hash,
            "taille": file_info_1.size,
            "engagements__num_ej": num_ej1,
        },
        {
            "file": file_info_2.file.name,
            "extension": "pdf",
            "hash": file_info_2.hash,
            "taille": file_info_2.size,
            "engagements__num_ej": num_ej2,
        },
    ]


@pytest.mark.django_db
def test_init_documents_from_external_handles_duplicate_file_info():
    # Create a file info
    file_info = FileInfoFactory()
    num_ej1 = "1234567890"
    ExternalLinkDocumentOrder.objects.create(document_external_id=file_info.external_id, order_external_id=num_ej1)
    # File info with same hash, same ej
    dup_file_info1 = FileInfoFactory(hash=file_info.hash)
    ExternalLinkDocumentOrder.objects.create(document_external_id=dup_file_info1.external_id, order_external_id=num_ej1)
    # File info with same hash, different ej
    dup_file_info2 = FileInfoFactory(hash=file_info.hash)
    num_ej2 = "2234567890"
    ExternalLinkDocumentOrder.objects.create(document_external_id=dup_file_info2.external_id, order_external_id=num_ej2)

    init_documents_from_external_filter_by_num_ejs([num_ej1, num_ej2], "batch1")

    batches = list(DataBatch.objects.values("ej__num_ej", "batch"))
    assert batches == [
        {"ej__num_ej": num_ej1, "batch": "batch1"},
        {"ej__num_ej": num_ej2, "batch": "batch1"},
    ]

    documents = list(Document.objects.values("hash", "engagements__num_ej"))
    assert documents == [
        {"hash": file_info.hash, "engagements__num_ej": num_ej1},
        {"hash": file_info.hash, "engagements__num_ej": num_ej2},
    ]


@pytest.mark.django_db
def test_init_documents_from_external_handles_duplicate_existing_document():
    # Existing document
    doc = DocumentFactory(hash="toto")
    # File info with same hash
    file_info = FileInfoFactory(hash=doc.hash)
    num_ej = "1234567890"
    ExternalLinkDocumentOrder.objects.create(document_external_id=file_info.external_id, order_external_id=num_ej)

    init_documents_from_external_filter_by_num_ejs([num_ej], "batch1")

    batches = list(DataBatch.objects.values("ej__num_ej", "batch"))
    assert batches == [
        {"ej__num_ej": num_ej, "batch": "batch1"},
    ]

    documents = list(Document.objects.values("hash", "engagements__num_ej"))
    assert documents == [
        {"hash": file_info.hash, "engagements__num_ej": num_ej},
    ]


@pytest.mark.django_db
def test_remove_duplicate_takes_shortest_path():
    """Make sure we pick the shortest path (minimal nesting level and shortest filename."""
    # Even if this file path is shorter, the nesting level is too high
    file_info2 = FileInfoFactory(file="f/a.zip_/t.pdf", hash="toto")
    # This is the shortest path (taking account nesting level and filename)
    file_info_expected = FileInfoFactory(file="folder/toto.pdf", hash="toto")
    # Same nesting level, but longer filename
    file_info3 = FileInfoFactory(file="folder/totofjfiufrr.pdf", hash="toto")

    result = remove_duplicates([file_info_expected, file_info2, file_info3])

    assert result == [file_info_expected]


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
        m_listdir.return_value = ([], [f"{str(i) * 10}_doc{i}.pdf" for i in range(1, number_of_files)])
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
        i = FileInfoFactory.build(external_id=None, filename=filename, folder=directory_path)
        data = {
            "filename": i.filename,
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
        assert files_info[0].filename == "0123456789_doc1.pdf"
        assert files_info[0].folder == gen_data_infos[0]["dossier"]
        assert files_info[0].file.name == "folder/0123456789_doc1.pdf"
        assert files_info[0].extension == gen_data_infos[0]["extension"]
        assert files_info[0].created_date == gen_data_infos[0]["date_creation"]
        assert files_info[0].size == gen_data_infos[0]["taille"]
        assert files_info[0].hash == gen_data_infos[0]["hash"]
        assert files_info[1].filename == "0987654321_doc2.pdf"
        assert files_info[1].folder == gen_data_infos[1]["dossier"]
        assert files_info[1].file.name == "folder/0987654321_doc2.pdf"
        assert files_info[1].extension == gen_data_infos[1]["extension"]
        assert files_info[1].created_date == gen_data_infos[1]["date_creation"]
        assert files_info[1].size == gen_data_infos[1]["taille"]
        assert files_info[1].hash == gen_data_infos[1]["hash"]

    with (
        patch("app.file_manager.cleaner.get_file_initial_info", autospec=True) as m_get_file_info,
        patch("docia.file_processing.pipeline.steps.init_documents.listdir_chunk", autospec=True) as m_listdir,
    ):
        m_get_file_info.side_effect = mock_get_file_initial_info
        m_listdir.return_value = ["0123456789_doc1.pdf", "0987654321_doc2.pdf"]
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
def test_bulk_create_documents():
    files_info = FileInfoFactory.create_batch(3)
    bulk_create_documents(files_info)
    assert_documents_equals_files_info(Document.objects.all(), files_info)


@pytest.mark.django_db
def test_bulk_create_documents_ignore_duplicates():
    file_info = FileInfoFactory()
    # Run the bulk_create twice
    bulk_create_documents([file_info])
    bulk_create_documents([file_info])
    # Assert only one inserted
    assert_documents_equals_files_info(Document.objects.all(), [file_info])


@pytest.mark.django_db
def test_bulk_create_links_doc_engagement_using_filenames():
    """Test that links between Documents and Engagements are created correctly (using filename)."""
    # Create Engagements
    ej1 = DataEngagementFactory()
    ej2 = DataEngagementFactory()
    ej3 = DataEngagementFactory()
    ej_list = [ej1, ej2, ej3]

    # Create FileInfo objects with filenames matching the Engagements
    files_info = [
        FileInfoFactory(external_id=None, filename=f"{ej1.num_ej}_doc1.pdf"),
        FileInfoFactory(external_id=None, filename=f"{ej2.num_ej}_doc2.pdf"),
        FileInfoFactory(external_id=None, filename=f"{ej3.num_ej}_doc3.pdf"),
    ]

    # Create Documents with the same hash and filename as the FileInfo objects
    for fi in files_info:
        DocumentFactory(hash=fi.hash, filename=fi.filename)

    # Call the function to create links between Documents and Engagements using filenames
    bulk_create_links_document_engagement_using_filenames(files_info)

    # Verify that the links were created correctly
    RelModel = Document.engagements.through
    links = list(RelModel.objects.order_by("document__filename").values("document__filename", "dataengagement__num_ej"))
    assert links == [
        {"document__filename": fi.filename, "dataengagement__num_ej": ej.num_ej} for fi, ej in zip(files_info, ej_list)
    ]


@pytest.mark.django_db
def test_bulk_create_links_doc_engagement_using_filenames_ignores_duplicates():
    """Test that links creation ignores duplicates (using filename).

    If a Document already has a link to an Engagement, the function should not create a duplicate link.
    """
    # Create an Engagement and a FileInfo
    ej = DataEngagementFactory()
    file_info = FileInfoFactory(external_id=None, filename=f"{ej.num_ej}_doc.pdf")

    # Create a Document with the same hash as the FileInfo and link it to the Engagement
    doc = DocumentFactory(hash=file_info.hash)
    doc.engagements.add(ej)

    # Call the function to create links between Documents and Engagements using filenames
    bulk_create_links_document_engagement_using_filenames([file_info])

    # Verify that no duplicate link was created
    RelModel = Document.engagements.through
    links = list(RelModel.objects.order_by("document__filename").values("document__filename", "dataengagement__num_ej"))
    assert links == [{"document__filename": doc.filename, "dataengagement__num_ej": ej.num_ej}]


@pytest.mark.django_db
def test_bulk_create_links_doc_engagement_using_external():
    """Test that links between Documents and Engagements are created correctly (using external data)."""
    files_info = FileInfoFactory.create_batch(3)
    expected_links = []
    for fi in files_info:
        ej = DataEngagementFactory()
        ExternalLinkDocumentOrder.objects.create(
            document_external_id=fi.external_id,
            order_external_id=ej.num_ej,
        )
        DocumentFactory(hash=fi.hash, file=fi.file)
        expected_links.append((fi.hash, ej.num_ej))

    # Call the function to create links between Documents and Engagements using external data
    bulk_create_links_document_engagement_using_external_data(files_info)

    # Verify that the links were created correctly
    RelModel = Document.engagements.through
    links = list(RelModel.objects.order_by("document__file").values_list("document__hash", "dataengagement__num_ej"))
    assert links == expected_links


@pytest.mark.django_db
def test_bulk_create_links_doc_engagement_using_external_ignores_duplicates():
    """Test that links creation ignores duplicates (using external data).

    If a Document already has a link to an Engagement, the function should not create a duplicate link.
    """
    file_info = FileInfoFactory()
    ej = DataEngagementFactory()
    ExternalLinkDocumentOrder.objects.create(
        document_external_id=file_info.external_id,
        order_external_id=ej.num_ej,
    )
    doc = DocumentFactory(hash=file_info.hash, file=file_info.file)
    doc.engagements.add(ej)
    bulk_create_links_document_engagement_using_external_data([file_info])
    RelModel = Document.engagements.through
    links = list(RelModel.objects.order_by("document__file").values_list("document__hash", "dataengagement__num_ej"))
    assert links == [(file_info.hash, ej.num_ej)]
