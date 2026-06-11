from datetime import datetime, timezone
from unittest import mock
from unittest.mock import patch

import pydantic
import pytest
import requests
import responses
from requests.exceptions import ConnectionError

from docia.file_processing.sync.client import (
    ApiDocumentMetadata,
    ApiEngagementActivity,
    SyncApiError,
    SyncClient,
    parse_api_datetime,
)

# TODO
#   - test authenticated failure
#   - test download non existent document
#   - test token expiration handling


@pytest.fixture
def client() -> SyncClient:
    """Create a SyncClient instance for testing using from_settings"""
    return SyncClient.from_settings()


def test_authenticate_success(client: SyncClient):
    """Test successful authentication"""
    # Mock successful authentication
    responses.add(
        responses.POST,
        "https://auth.api.testing.beta.gouv.fr/oauth/token",
        json={"access_token": "test_token_123"},
        status=200,
    )

    # Call authenticate
    client.authenticate()

    # Verify the token was set
    assert client.token == "test_token_123"
    assert client.session.headers["Authorization"] == "Bearer test_token_123"


def test_list_documents_for_ej_success(client: SyncClient):
    """Test successful document listing"""

    # Mock the document listing response
    mock_response = {
        "d": {
            "results": [
                {
                    "id_pj": "doc123",
                    "nom_pj": "test_document.pdf",
                    "num_ej": "EJ2023-001",
                    "size_pj": "1024",
                    "date_pj": "/Date(1774001460000)/",  # 2026-03-20 10:11:00 UTC
                }
            ],
        }
    }
    responses.add(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_metadata",
        json=mock_response,
        status=200,
    )

    # List documents
    documents = client.list_documents_for_ej("EJ2023-001")

    # Verify the response
    assert documents == [
        ApiDocumentMetadata(
            id="doc123",
            name="test_document.pdf",
            num_ej="EJ2023-001",
            size=1024,
            date=datetime(2026, 3, 20, 10, 11, tzinfo=timezone.utc),
        )
    ]


def test_list_documents_for_ej_validation_error(client: SyncClient, caplog):
    """Test validation error handling"""

    # Mock invalid response (missing required fields)
    mock_response = {
        "d": {
            "results": [
                {
                    "id_pj": "doc123",
                    # Missing nom_pj, num_ej, size_pj, date_pj
                }
            ]
        }
    }
    responses.add(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_metadata",
        json=mock_response,
        status=200,
    )

    # List and expect validation error
    with pytest.raises(pydantic.ValidationError):
        client.list_documents_for_ej("EJ2023-001")

    # Verify that a warning was logged
    assert "Validation error for document" in caplog.text


def test_list_documents_for_ej_invalid_size(client: SyncClient, caplog):
    """Test handling of invalid size_pj values"""

    # Mock response with invalid size_pj (not an integer)
    mock_response = {
        "d": {
            "results": [
                {
                    "id_pj": "doc123",
                    "nom_pj": "test_document.pdf",
                    "num_ej": "EJ2023-001",
                    "size_pj": "invalid_size",  # Not a valid integer
                    "date_pj": "/Date(1774001460000)/",  # 2026-03-20 10:11:00 UTC
                }
            ]
        }
    }
    responses.add(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_metadata",
        json=mock_response,
        status=200,
    )

    # List documents
    documents = client.list_documents_for_ej("EJ2023-001")

    # Verify the response - should default size to -1
    assert documents[0].size == -1

    # Verify that a warning was logged about invalid size
    assert "Invalid size_pj value" in caplog.text
    assert "defaulting to -1" in caplog.text


def test_list_documents_for_ej_deduplication(client: SyncClient):
    """Test that duplicate documents are properly removed"""

    doc_data = {
        "id_pj": "doc123",
        "nom_pj": "test_document.pdf",
        "num_ej": "EJ2023-001",
        "size_pj": "1024",
        "date_pj": "/Date(1774001460000)/",
    }

    # Mock response with duplicate documents (same id_pj)
    mock_response = {
        "d": {
            "results": [
                {**doc_data, "date_pj": "/Date(1774001470000)/"},  # Different date but later
                doc_data,
                {**doc_data},  # Strictly same, should be deduplicated
                {**doc_data, "date_pj": "/Date(1774001470000)/"},  # Different date but later
                {
                    "id_pj": "doc456",
                    "nom_pj": "another_document.pdf",
                    "num_ej": "EJ2023-001",
                    "size_pj": "2048",
                    "date_pj": "/Date(1774001460000)/",
                },
            ]
        }
    }
    responses.add(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_metadata",
        json=mock_response,
        status=200,
    )

    # List documents
    documents = client.list_documents_for_ej("EJ2023-001")

    # Verify that duplicates are removed - should only have 2 unique documents
    expected = [
        ApiDocumentMetadata(
            id="doc123",
            name="test_document.pdf",
            num_ej="EJ2023-001",
            size=1024,
            date=datetime(2026, 3, 20, 10, 11, tzinfo=timezone.utc),
        ),
        ApiDocumentMetadata(
            id="doc456",
            name="another_document.pdf",
            num_ej="EJ2023-001",
            size=2048,
            date=datetime(2026, 3, 20, 10, 11, tzinfo=timezone.utc),
        ),
    ]
    assert documents == expected


@pytest.mark.parametrize(
    "dict_overwrite",
    [
        {"nom_pj": "different_name.pdf"},
        {"size_pj": "1111"},
        {"num_ej": "EJ2023-002"},
    ],
)
def test_list_documents_for_ej_invalid_duplicate(client: SyncClient, dict_overwrite):
    """Test that invalid duplicates (different metadata) raise an error"""

    # Mock response with invalid duplicate (same ID but different metadata)
    doc_data = {
        "id_pj": "doc123",
        "nom_pj": "test_document.pdf",
        "num_ej": "EJ2023-001",
        "size_pj": "1024",
        "date_pj": "/Date(1774001460000)/",
    }
    invalid_dup_doc = {**doc_data, **dict_overwrite}
    mock_response = {
        "d": {
            "results": [
                doc_data,
                invalid_dup_doc,
            ]
        }
    }
    responses.add(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_metadata",
        json=mock_response,
        status=200,
    )

    # List documents and expect ValueError for invalid duplicate
    with pytest.raises(ValueError) as exc_info:
        client.list_documents_for_ej("EJ2023-001")

    # Verify the error message
    assert "Invalid duplicate" in str(exc_info.value)


def test_download_document_success(client: SyncClient):
    """Test successful document download"""

    # Mock document content
    test_content = b"test document content"
    responses.add(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_data('doc123')/$value",
        body=test_content,
        status=200,
    )

    # Download
    content = client.download_document("doc123")

    # Verify content
    assert content == test_content


def test_list_ej_place_success(client: SyncClient):
    """Test successful listing of engagement activities"""

    # Mock the engagement activity listing response
    mock_response = {
        "d": {
            "results": [
                {
                    "alerte": "Création",
                    "num_ej": "EJ2023-001",
                    "date_reception": "/Date(1672531200000)/",  # 2023-01-01 00:00:00 UTC
                    "pur_org": "OA123",
                    "pur_group": "GA456",
                },
                {
                    "alerte": "Modification",
                    "num_ej": "EJ2023-002",
                    "date_reception": "/Date(1672617600000)/",  # 2023-01-02 00:00:00 UTC
                    "pur_org": "OA123",
                    "pur_group": "GA456",
                },
            ]
        }
    }
    responses.add(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/liste_ej_place",
        json=mock_response,
        status=200,
    )

    # Define date range
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 2, 23, 59, 59, tzinfo=timezone.utc)

    # List engagement activities
    activities = client.list_ej_place(start=start_date, end=end_date, purchase_organization="OA123")

    # Verify the response
    assert len(activities) == 2

    # Verify first activity (CREATE)
    assert activities[0].type == ApiEngagementActivity.Type.CREATE
    assert activities[0].num_ej == "EJ2023-001"
    assert activities[0].purchase_organization == "OA123"
    assert activities[0].purchase_group == "GA456"
    assert activities[0].received_at == datetime(2023, 1, 1, tzinfo=timezone.utc)

    # Verify second activity (UPDATE)
    assert activities[1].type == ApiEngagementActivity.Type.UPDATE
    assert activities[1].num_ej == "EJ2023-002"
    assert activities[1].purchase_organization == "OA123"
    assert activities[1].purchase_group == "GA456"
    assert activities[1].received_at == datetime(2023, 1, 2, tzinfo=timezone.utc)


def test_list_ej_place_validation_error(client: SyncClient, caplog):
    """Test validation error handling for engagement activities"""

    # Mock invalid response (missing required fields)
    mock_response = {
        "d": {
            "results": [
                {
                    "alerte": "Création",
                    # Missing num_ej, date_reception, pur_org, pur_group
                }
            ]
        }
    }
    responses.add(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/liste_ej_place",
        json=mock_response,
        status=200,
    )

    # Define date range
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 2, 23, 59, 59, tzinfo=timezone.utc)

    # List and expect validation error
    with pytest.raises(pydantic.ValidationError):
        client.list_ej_place(start=start_date, end=end_date, purchase_organization="OA123")

    # Verify that a warning was logged
    assert "Validation error for object" in caplog.text


def test_token_expired(client: SyncClient, caplog):
    """Test that token expiration (401) triggers re-authentication and retry in _retry_call"""

    with (
        patch.object(client, "authenticate", autospec=True) as m_authenticate,
        patch("time.sleep", autospec=True) as m_sleep,
    ):
        # Track call count
        call_count = 0

        def api_call():
            nonlocal call_count
            call_count += 1
            # First call, authenticate should not have been called yet
            if call_count == 1:
                assert m_authenticate.call_count == 0
            # Return failure if not authenticated, else success
            if m_authenticate.call_count < 1:
                raise requests.HTTPError(
                    "401 Unauthorized",
                    response=type("MockResponse", (), {"status_code": 401, "text": "Token expired"})(),
                )
            else:
                return "success_result"

        # Call _retry_call
        result = client._retry_call(api_call, max_retries=0, retry_delay=0)

    # Verify authenticate and sleep have been called
    assert m_authenticate.call_count == 1
    assert m_sleep.call_count == 1

    # Verify the call succeeded after re-authentication
    assert result == "success_result"
    assert call_count == 2  # Should have been called twice

    # Verify warning was logged about 401
    assert "401, wait " in caplog.text
    assert " before retry (1/1)" in caplog.text


def test_download_document_api_error(client: SyncClient, caplog):
    """Test that download_document handles API errors and implements retry logic"""

    # Track call count to return different responses
    call_count = 0

    def request_callback(request):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # First two calls return 429 (rate limited)
            return (429, {}, "Rate limited")
        else:
            # Third call succeeds
            return (200, {}, b"test document content")

    # Add response with callback that handles multiple calls
    responses.add_callback(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_data('doc123')/$value",
        callback=request_callback,
    )

    # Call download_document with retries
    with (
        patch("time.sleep", autospec=True) as m_sleep,
        patch("random.random", autospec=True, return_value=0.5),
    ):
        content = client.download_document("doc123", max_retries=3, retry_delay=20)

    # Verify the call succeeded after retries
    assert content == b"test document content"

    # Verify sleep was called exactly twice with correct values (exponential backoff with jitter)
    m_sleep.assert_has_calls(
        [
            mock.call(20 * 1.05 * 1),  # First retry: retry_delay * 1.05 * (attempt + 1)
            mock.call(20 * 1.05 * 2),  # Second retry: retry_delay * 1.05 * (attempt + 1)
        ],
        any_order=False,
    )  # Ensure calls were made in this exact order
    assert m_sleep.call_count == 2  # Ensure no extra calls were made

    # Verify warning was logged about 429
    assert "429, wait " in caplog.text
    assert " before retry" in caplog.text


def test_download_document_connection_error(client: SyncClient, caplog):
    """Test that download_document handles connection errors and implements retry logic"""

    # Track call count to return different responses
    call_count = 0

    def request_callback(request):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # First two calls fail
            raise ConnectionError(None, request=request)
        else:
            # Third call succeeds
            return (200, {}, b"test document content")

    # Add response with callback that handles multiple calls
    responses.add_callback(
        responses.GET,
        "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_data('doc123')/$value",
        callback=request_callback,
    )

    # Call download_document with retries
    with (
        patch("time.sleep", autospec=True) as m_sleep,
        patch("random.random", autospec=True, return_value=0.5),
    ):
        content = client.download_document("doc123", max_retries=3, retry_delay=20)

    # Verify the call succeeded after retries
    assert content == b"test document content"

    # Verify sleep was called exactly twice with correct values (exponential backoff with jitter)
    m_sleep.assert_has_calls(
        [
            mock.call(20 * 1.05 * 1),  # First retry: retry_delay * 1.05 * (attempt + 1)
            mock.call(20 * 1.05 * 2),  # Second retry: retry_delay * 1.05 * (attempt + 1)
        ],
        any_order=False,
    )  # Ensure calls were made in this exact order
    assert m_sleep.call_count == 2  # Ensure no extra calls were made

    # Verify warning was logged about 429
    assert "-1, wait " in caplog.text
    assert " before retry" in caplog.text


def test_download_document_api_error_exhausted_retries(client: SyncClient, caplog):
    """Test that download_document raises exception after exhausting all retries"""

    # Mock API calls that always return 429 (rate limited)
    # responses will use these in order: first for initial call, then for retries
    url = "https://filesync.api.testing.beta.gouv.fr/export_pj_ej/pieces_jointes_data('doc123')/$value"
    responses.add(
        responses.GET,
        url,
        status=429,
    )

    # Call download_document with limited retries and expect exception
    with (
        patch("time.sleep", autospec=True) as m_sleep,
        patch("random.random", autospec=True, return_value=0.5),
        pytest.raises(SyncApiError) as exc_info,
    ):
        client.download_document("doc123", max_retries=2, retry_delay=20)

    # Verify the exception was raised and wrapped correctly
    assert exc_info.value.code == "HTTP_429"
    assert "429" in exc_info.value.message

    # Verify sleep was called exactly 2 times (max_retries=2 means 2 retry attempts)
    assert m_sleep.call_count == 2
    m_sleep.assert_has_calls(
        [
            mock.call(20 * 1.05 * 1),  # First retry: retry_delay * 1.05 * (attempt + 1)
            mock.call(20 * 1.05 * 2),  # Second retry: retry_delay * 1.05 * (attempt + 1)
        ],
        any_order=False,
    )

    # Verify total calls: 1 initial + 2 retries = 3 total calls
    assert [call.request.url for call in responses.calls] == [url] * 3

    # Verify warning was logged about 429 for each retry
    assert caplog.text.count("429, wait ") == 2


# --- parse_api_datetime tests ---


def test_parse_api_datetime_valid():
    """Test parsing valid API datetime format"""

    # Test with a specific timestamp (2023-01-01 00:00:00 UTC)
    # 1672531200000 ms = 2023-01-01 00:00:00 UTC
    result = parse_api_datetime("/Date(1672531200000)/")
    expected = datetime(2023, 1, 1, tzinfo=timezone.utc)
    assert result == expected

    # Test with another timestamp (2023-01-02 12:34:56 UTC)
    # Calculate timestamp: datetime(2023, 1, 2, 12, 34, 56).timestamp() * 1000
    result = parse_api_datetime("/Date(1672662896000)/")
    expected = datetime(2023, 1, 2, 12, 34, 56, tzinfo=timezone.utc)
    assert result == expected


@pytest.mark.parametrize(
    "invalid_format",
    [
        "/Date(-86400000)/",  # Negative timestamp
        "Date(1234567890)",  # Missing leading slash
        "/Date(1234567890)",  # Missing trailing slash
        "/Date(abc)/",  # Non-numeric timestamp
        "/Date()/",  # Empty timestamp
        "1234567890",  # Just a timestamp
        "",  # Empty string
    ],
)
def test_parse_api_datetime_invalid_format(invalid_format):
    """Test that invalid formats raise ValueError"""
    with pytest.raises(ValueError) as exc_info:
        parse_api_datetime(invalid_format)
    assert "Invalid datetime format" in str(exc_info.value)


def test_parse_api_datetime_valid_with_milliseconds():
    """Test valid format with milliseconds precision"""
    result = parse_api_datetime("/Date(1234567890123)/")
    expected = datetime(2009, 2, 13, 23, 31, 30, 123000, tzinfo=timezone.utc)
    assert result == expected


def test_parse_api_datetime_edge_cases():
    """Test edge cases and boundary conditions"""
    # Test with very large timestamp (year 2100)
    result = parse_api_datetime("/Date(4102444800000)/")  # 2100-01-01 00:00:00 UTC
    expected = datetime(2100, 1, 1, tzinfo=timezone.utc)
    assert result == expected

    # Test with timestamp 0 (1970-01-01 00:00:00 UTC)
    result = parse_api_datetime("/Date(0)/")
    expected = datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert result == expected

    # Test with timestamp including milliseconds
    result = parse_api_datetime("/Date(1672531200500)/")  # 2023-01-01 00:00:00.500 UTC
    expected = datetime(2023, 1, 1, 0, 0, 0, 500000, tzinfo=timezone.utc)
    assert result == expected
