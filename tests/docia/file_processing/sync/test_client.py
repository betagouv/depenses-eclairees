import pydantic
import pytest
import responses

from docia.file_processing.sync.client import ApiDocumentMetadata, SyncClient

# TODO
#   - test authenticated failure
#   - test download non existent document
#   - test token expiration handling


@pytest.fixture
def client():
    """Create a SyncClient instance for testing using from_settings"""
    return SyncClient.from_settings()


@responses.activate
def test_authenticate_success(client):
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


@responses.activate
def test_list_documents_for_ej_success(client):
    """Test successful document listing"""

    # Mock the document listing response
    mock_response = {
        "d": {
            "results": [{"id_pj": "doc123", "nom_pj": "test_document.pdf", "num_ej": "EJ2023-001", "size_pj": "1024"}]
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
        )
    ]


@responses.activate
def test_list_documents_for_ej_validation_error(client, caplog):
    """Test validation error handling"""

    # Mock invalid response (missing required fields)
    mock_response = {
        "d": {
            "results": [
                {
                    "id_pj": "doc123",
                    # Missing nom_pj, num_ej, size_pj
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


@responses.activate
def test_list_documents_for_ej_invalid_size(client, caplog):
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


@responses.activate
def test_download_document_success(client):
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
