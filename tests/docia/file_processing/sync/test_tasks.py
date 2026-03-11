from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import freezegun
import pytest

from docia.file_processing.sync.tasks import (
    _default_start_datetime,
    download_documents,
    sync_documents,
    sync_engagements,
)
from tests.factories.data import DataEngagementFactory
from tests.factories.file_processing import (
    ExternalDocumentMetadataFactory,
    ExternalLinkDocumentOrderFactory,
)


@pytest.fixture(autouse=True)
def mock_file_sync_scopes(settings):
    """Mock FILE_SYNC_SCOPES setting for all tests in this file"""
    settings.FILE_SYNC_SCOPES = ["oa/ga"]


@pytest.mark.django_db
def test_default_start_datetime():
    """Test that _default_start_datetime returns a datetime 7 days ago from now"""
    with freezegun.freeze_time("2024-03-15 12:00:00", tz_offset=0):
        result = _default_start_datetime()
        expected = datetime(2024, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        assert result == expected


@pytest.mark.django_db
def test_sync_engagements():
    """Test that sync_engagements calls EngagementsSync.sync with correct parameters"""

    now = datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    with freezegun.freeze_time(now):
        with patch("docia.file_processing.sync.tasks.EngagementsSync") as MockEngagementsSync:
            # Create a mock instance
            mock_instance = MockEngagementsSync.return_value
            mock_instance.sync = MagicMock(autospec=True)

            sync_engagements()

            # Verify EngagementsSync was instantiated and sync was called
            expected_start = datetime(2024, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
            mock_instance.sync.assert_called_once_with([["oa", "ga"]], expected_start, now)


@pytest.mark.django_db
def test_sync_documents():
    """Test that sync_documents fetches engagements and calls DocumentMetadataSync.sync"""
    start = datetime(2024, 3, 1, tzinfo=timezone.utc)

    # Create test engagements
    ej1 = DataEngagementFactory(external_updated_at=datetime(2024, 3, 2, tzinfo=timezone.utc))
    ej2 = DataEngagementFactory(external_updated_at=datetime(2024, 3, 3, tzinfo=timezone.utc))
    # This engagement should not be included (updated before start date)
    DataEngagementFactory(external_updated_at=datetime(2024, 2, 28, tzinfo=timezone.utc))

    with patch("docia.file_processing.sync.tasks.DocumentMetadataSync") as MockDocumentMetadataSync:
        # Create a mock instance
        mock_instance = MockDocumentMetadataSync.return_value
        mock_instance.sync = MagicMock(autospec=True)

        sync_documents(start=start)

        # Verify DocumentMetadataSync was instantiated and sync was called
        MockDocumentMetadataSync.assert_called_once()
        # Verify it was called with the correct order_ids (ordered by -external_updated_at)
        call_args = mock_instance.sync.call_args
        actual_order_ids = call_args[0][0]  # Get the list of order IDs passed to sync()
        expected_order_ids = [ej1.num_ej, ej2.num_ej]  # Expected order: older first, newer second
        assert actual_order_ids == expected_order_ids


@pytest.mark.django_db
def test_download_documents():
    """Test that download_documents fetches documents and downloads them"""
    start = datetime(2024, 3, 1, tzinfo=timezone.utc)

    # Create test engagements
    ej1 = DataEngagementFactory(external_updated_at=datetime(2024, 3, 2, tzinfo=timezone.utc))
    ej2 = DataEngagementFactory(external_updated_at=datetime(2024, 3, 3, tzinfo=timezone.utc))

    # Create test documents
    doc1 = ExternalDocumentMetadataFactory(name="document1.pdf")
    doc2 = ExternalDocumentMetadataFactory(name="document2.pdf")

    # Link documents to engagements
    ExternalLinkDocumentOrderFactory(external_document=doc1, order_id=ej1.num_ej)
    ExternalLinkDocumentOrderFactory(external_document=doc2, order_id=ej2.num_ej)

    with patch("docia.file_processing.sync.tasks.DocumentDownloader") as MockDocumentDownloader:
        # Create a mock instance
        mock_instance = MockDocumentDownloader.return_value
        mock_instance.download_document = MagicMock(autospec=True)

        download_documents(start=start)

        # Verify DocumentDownloader was instantiated and download_document was called
        MockDocumentDownloader.assert_called_once()
        assert mock_instance.download_document.call_count == 2
        mock_instance.download_document.assert_any_call(doc1.external_id, doc1.name)
        mock_instance.download_document.assert_any_call(doc2.external_id, doc2.name)
