from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import freezegun
import pytest

from docia.file_processing.sync.workflow import (
    download_documents,
    sync_documents,
    sync_engagements,
)
from tests.factories.data import DataEngagementFactory
from tests.factories.file_processing import (
    ExternalDocumentMetadataFactory,
)


@pytest.fixture(autouse=True)
def mock_file_sync_scopes(settings):
    """Mock FILE_SYNC_SCOPES setting for all tests in this file"""
    settings.FILE_SYNC_SCOPES = ["oa/ga"]


@pytest.mark.django_db
def test_sync_engagements():
    """Test that sync_engagements calls EngagementsSync.sync with correct parameters"""

    now = datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    with freezegun.freeze_time(now):
        with patch("docia.file_processing.sync.workflow.EngagementsSync") as MockEngagementsSync:
            # Create a mock instance
            mock_instance = MockEngagementsSync.return_value
            mock_instance.sync = MagicMock(autospec=True)

            sync_engagements(now - timedelta(days=7))

            # Verify EngagementsSync was instantiated and sync was called
            expected_start = datetime(2024, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
            mock_instance.sync.assert_called_once_with([["oa", "ga"]], expected_start, now)


@pytest.mark.django_db
def test_sync_documents():
    """Test that sync_documents fetches engagements and calls DocumentMetadataSync.sync"""

    # Create test engagements
    ej1 = DataEngagementFactory(external_updated_at=datetime(2024, 3, 2, tzinfo=timezone.utc))
    ej2 = DataEngagementFactory(external_updated_at=datetime(2024, 3, 3, tzinfo=timezone.utc))
    # This engagement should not be included (updated before start date)
    DataEngagementFactory(external_updated_at=datetime(2024, 2, 28, tzinfo=timezone.utc))

    with patch("docia.file_processing.sync.workflow.DocumentMetadataSync") as MockDocumentMetadataSync:
        # Create a mock instance
        mock_instance = MockDocumentMetadataSync.return_value
        mock_instance.sync = MagicMock(autospec=True)

        sync_documents([ej1.num_ej, ej2.num_ej])

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

    # Create test documents
    doc1 = ExternalDocumentMetadataFactory(name="document1.pdf", size=35 * 1000 * 1000)  # No retry
    doc2 = ExternalDocumentMetadataFactory(name="document2.pdf", size=1000)  # Retry activated

    with patch(
        "docia.file_processing.sync.workflow.DocumentDownloader.download_document", autospec=True
    ) as m_download_document:
        download_documents([doc1.external_id, doc2.external_id])

        # Verify download_document was called
        assert m_download_document.call_count == 2
        calls = [(c.args[1:], c.kwargs) for c in m_download_document.call_args_list]
        assert sorted(calls) == sorted(
            [
                ((doc1.external_id, doc1.name), dict(max_retries=0)),
                ((doc2.external_id, doc2.name), dict(max_retries=2)),
            ]
        )
