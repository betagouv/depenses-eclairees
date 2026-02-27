import io
import zipfile
from unittest.mock import patch

from django.core.files.storage import default_storage

import pytest

from docia.file_processing.models import FileInfo
from docia.file_processing.sync.downloader import DocumentDownloader
from tests.factories.file_processing import FileInfoFactory
from tests.utils import assert_queryset_equal


@pytest.fixture
def downloader():
    downloader = DocumentDownloader()
    downloader.client.is_authenticated = True
    yield downloader


@pytest.mark.django_db
def test_generic_file_handling(downloader):
    """Test that generic (non-zip) files are handled correctly"""

    with (
        patch.object(downloader.client, "download_document", autospec=True) as m_client_download,
    ):
        # Create simple text content
        text_content = b"Simple text content"
        m_client_download.return_value = text_content

        # Test data
        external_id = "test_external_id_text"
        name = "simple_file.txt"

        # Call the download method
        downloader.download_document(external_id, name)

        # Check that the file was stored
        file_infos = FileInfo.objects.filter(external_id=external_id)

        # We should have only 1 file
        assert len(file_infos) == 1

        file_info = file_infos[0]

        # Check the file content
        with default_storage.open(file_info.file.name, "rb") as f:
            stored_content = f.read()
        assert stored_content == text_content

        # Check all FileInfo attributes (except created_at and updated_at as requested)
        assert file_info.external_id == external_id
        assert file_info.parent is None
        assert file_info.filename == "simple_file.txt"
        assert file_info.folder == f"docs/{external_id}"
        assert file_info.extension == "txt"
        assert file_info.size == len(text_content)
        assert file_info.hash is not None
        assert len(file_info.hash) == 64  # SHA256 hash length
        assert file_info.original_filename == name

        # Check that the file field is properly set
        expected_filepath = f"docs/{external_id}/simple_file.txt"
        assert file_info.file is not None
        assert file_info.file.name == expected_filepath


@pytest.mark.django_db
def test_existing_fileinfo_skip_processing(downloader, caplog):
    """Test that download is skipped when FileInfo already exists"""

    with (
        patch.object(downloader.client, "download_document", autospec=True) as m_client_download,
    ):
        # Create simple text content
        text_content = b"This should not be downloaded"
        m_client_download.return_value = text_content

        # Test data
        external_id = "test_external_id_exists"
        name = "existing_file.txt"

        # Create an existing FileInfo record
        existing_fileinfo = FileInfoFactory(
            external_id=external_id,
        )

        # Call the download method
        downloader.download_document(external_id, name)

        # Check that download_document was NOT called (file already exists)
        m_client_download.assert_not_called()

        # Check that no new FileInfo was created
        assert_queryset_equal(FileInfo.objects.all(), [existing_fileinfo])

        # Check that a log message was recorded
        assert "Skip file" in caplog.text
        assert external_id in caplog.text
        assert name in caplog.text


@pytest.mark.django_db
def test_invalid_zip_file_handling(downloader, caplog):
    """Test that invalid zip files are handled gracefully"""

    with (
        patch.object(downloader.client, "download_document", autospec=True) as m_client_download,
    ):
        invalid_zip_content = b"This is not a valid zip file"
        m_client_download.return_value = invalid_zip_content

        # Test data
        external_id = "test_external_id_invalid"
        name = "invalid_archive.zip"

        with pytest.raises(zipfile.BadZipFile):
            # Call the download method
            downloader.download_document(external_id, name)

        # Check that nothing is stored
        assert not FileInfo.objects.filter(external_id=external_id).exists()

        # Check that an error was logged
        assert "File is not a valid zip file" in caplog.text or "Error extracting zip file" in caplog.text


@pytest.mark.django_db
def test_zip_file_with_nested_structure(downloader):
    """Test that zip files are handled correctly"""

    with (
        patch.object(downloader.client, "download_document", autospec=True) as m_client_download,
    ):
        # Create zip file in memory with two text files and an other zip
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("hello1.txt", b"Content of hello1")
            zip_file.writestr("hello2.txt", b"Content of hello2")
            zip_file.writestr("sub/hello3.txt", b"Content of hello3")
            zip_buffer_2 = io.BytesIO()
            with zipfile.ZipFile(zip_buffer_2, "w") as zip_file_2:
                zip_file_2.writestr("toto1.txt", b"Content of toto1")
                zip_file_2.writestr("toto2.txt", b"Content of toto2")
                zip_file_2.writestr("zzz/sub/toto3.txt", b"Content of toto3")
            zip_file.writestr("subarchive.zip", zip_buffer_2.getvalue())

        zip_content = zip_buffer.getvalue()

        # Mock the client to return our zip content
        m_client_download.return_value = zip_content

        # Test data
        external_id = "test_external_id"
        name = "archive.zip"

        # Call the download method
        downloader.download_document(external_id, name)

        # Check that the zip file and its contents were stored
        files_info = FileInfo.objects.order_by("file")

        # Check the filenames
        files = [fi.file.name for fi in files_info]

        # Check that we have the expected files
        prefix = f"docs/{external_id}/"
        expected_files = [
            f"{prefix}archive.zip",
            f"{prefix}archive.zip_/hello1.txt",
            f"{prefix}archive.zip_/hello2.txt",
            f"{prefix}archive.zip_/sub/hello3.txt",
            f"{prefix}archive.zip_/subarchive.zip",
            f"{prefix}archive.zip_/subarchive.zip_/toto1.txt",
            f"{prefix}archive.zip_/subarchive.zip_/toto2.txt",
            f"{prefix}archive.zip_/subarchive.zip_/zzz/sub/toto3.txt",
        ]

        assert files == expected_files

        def read_file(filepath):
            with default_storage.open(filepath, "rb") as f:
                return f.read()

        assert read_file(f"{prefix}archive.zip_/hello1.txt") == b"Content of hello1"
        assert read_file(f"{prefix}archive.zip") == zip_content
        assert read_file(f"{prefix}archive.zip_/hello1.txt") == b"Content of hello1"
        assert read_file(f"{prefix}archive.zip_/hello2.txt") == b"Content of hello2"
        assert read_file(f"{prefix}archive.zip_/sub/hello3.txt") == b"Content of hello3"
        assert read_file(f"{prefix}archive.zip_/subarchive.zip") == zip_buffer_2.getvalue()
        assert read_file(f"{prefix}archive.zip_/subarchive.zip_/toto1.txt") == b"Content of toto1"
        assert read_file(f"{prefix}archive.zip_/subarchive.zip_/toto2.txt") == b"Content of toto2"
        assert read_file(f"{prefix}archive.zip_/subarchive.zip_/zzz/sub/toto3.txt") == b"Content of toto3"


def test_clean_filename_basic(downloader):
    """Test basic filename cleaning functionality"""

    # Test basic filename
    result = downloader.clean_filename("simple_file.txt")
    assert result == "simple_file.txt"

    # Test filename with slashes (should be replaced with underscores)
    result = downloader.clean_filename("path/to/file.txt")
    assert result == "path_to_file.txt"

    # Test filename with anti-slashes (should be replaced with underscores)
    result = downloader.clean_filename("path\\to\\file.txt")
    assert result == "path_to_file.txt"

    # Test filename with special characters that need unidecode
    result = downloader.clean_filename("fichier_avec_glaçon.txt")
    assert result == "fichier_avec_glacon.txt"

    # Test filename with accents that should be preserved
    result = downloader.clean_filename("fichier_éèêà.txt")
    assert result == "fichier_éèêà.txt"

    # Test mixed case extension (should be lowercased)
    result = downloader.clean_filename("file.TXT")
    assert result == "file.txt"


def test_clean_filename_length_truncation(downloader):
    """Test filename length truncation"""

    # Test filename that exceeds maximum length (250 chars total, including extension)
    long_filename = "a" * 300 + ".txt"
    result = downloader.clean_filename(long_filename)

    # Should be truncated to 250 chars total
    assert len(result) <= 250
    assert result.endswith(".txt")
    assert result.endswith("[trunc].txt")

    # Test with longer extension
    long_filename = "a" * 300 + ".pdf"
    result = downloader.clean_filename(long_filename)
    assert len(result) <= 250
    assert result.endswith(".pdf")
    assert result.endswith("[trunc].pdf")


def test_clean_filename_edge_cases(downloader):
    """Test edge cases for filename cleaning"""

    # Test empty filename
    result = downloader.clean_filename("")
    assert result == ""

    # Test filename with only extension
    result = downloader.clean_filename(".txt")
    assert result == ".txt"

    # Test filename with multiple dots
    result = downloader.clean_filename("file.with.multiple.dots.txt")
    assert result == "file.with.multiple.dots.txt"

    # Test filename with no extension
    result = downloader.clean_filename("file_without_extension")
    assert result == "file_without_extension"
