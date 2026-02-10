"""
Test cases for the Django admin interface, specifically for Document administration.
Tests the search functionality on the engagements__num_ej field.
"""

from django.urls import reverse

import pytest

from tests.factories.data import DataEngagementFactory, DocumentFactory


@pytest.mark.django_db
def test_document_admin_search_by_engagements_num_ej(admin_client):
    """Test that DocumentAdmin search works correctly on engagements__num_ej field"""
    # Create test engagements with specific num_ej values
    engagement1 = DataEngagementFactory(num_ej="EJ001")
    engagement2 = DataEngagementFactory(num_ej="EJ002")
    engagement3 = DataEngagementFactory(num_ej="EJ003")

    # Create documents and associate them with engagements
    # Document 1: associated with EJ001
    doc1 = DocumentFactory(filename="doc_with_EJ001.pdf")
    doc1.engagements.add(engagement1)

    # Document 2: associated with EJ002
    doc2 = DocumentFactory(filename="doc_with_EJ002.pdf")
    doc2.engagements.add(engagement2)

    # Document 3: associated with EJ001 and EJ003
    doc3 = DocumentFactory(filename="doc_with_EJ001_and_EJ003.pdf")
    doc3.engagements.add(engagement1, engagement3)

    # Document 4: no engagements (should not appear in search results)
    _doc4 = DocumentFactory(filename="doc_without_engagements.pdf")

    # Get the document list URL
    list_url = reverse("admin:docia_document_changelist")

    # Test 1: Search for EJ001 - should find doc1 and doc3
    search_url = f"{list_url}?q=EJ001"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that documents with EJ001 appear in results
    assert "doc_with_EJ001.pdf" in str(response.content)
    assert "doc_with_EJ001_and_EJ003.pdf" in str(response.content)

    # Check that documents without EJ001 do not appear
    assert "doc_with_EJ002.pdf" not in str(response.content)
    assert "doc_without_engagements.pdf" not in str(response.content)

    # Test 2: Search for EJ002 - should find only doc2
    search_url = f"{list_url}?q=EJ002"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that only doc2 appears
    assert "doc_with_EJ002.pdf" in str(response.content)
    assert "doc_with_EJ001.pdf" not in str(response.content)
    assert "doc_with_EJ001_and_EJ003.pdf" not in str(response.content)
    assert "doc_without_engagements.pdf" not in str(response.content)

    # Test 3: Search for EJ003 - should find only doc3
    search_url = f"{list_url}?q=EJ003"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that only doc3 appears
    assert "doc_with_EJ001_and_EJ003.pdf" in str(response.content)
    assert "doc_with_EJ001.pdf" not in str(response.content)
    assert "doc_with_EJ002.pdf" not in str(response.content)
    assert "doc_without_engagements.pdf" not in str(response.content)

    # Test 4: Search for non-existent EJ - should find no documents
    search_url = f"{list_url}?q=EJ999"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that no documents appear
    assert "doc_with_EJ001.pdf" not in str(response.content)
    assert "doc_with_EJ002.pdf" not in str(response.content)
    assert "doc_with_EJ001_and_EJ003.pdf" not in str(response.content)
    assert "doc_without_engagements.pdf" not in str(response.content)


@pytest.mark.django_db
def test_document_admin_search_by_partial_engagements_num_ej(admin_client):
    """Test that DocumentAdmin search works with partial matches on engagements__num_ej"""
    # Create test engagements
    engagement1 = DataEngagementFactory(num_ej="EJ12345")
    engagement2 = DataEngagementFactory(num_ej="EJ67890")

    # Create documents
    doc1 = DocumentFactory(filename="doc_with_EJ12345.pdf")
    doc1.engagements.add(engagement1)

    doc2 = DocumentFactory(filename="doc_with_EJ67890.pdf")
    doc2.engagements.add(engagement2)

    # Test partial search for "EJ123" - should find doc1
    list_url = reverse("admin:docia_document_changelist")
    search_url = f"{list_url}?q=EJ123"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    assert "doc_with_EJ12345.pdf" in str(response.content)
    assert "doc_with_EJ67890.pdf" not in str(response.content)


@pytest.mark.django_db
def test_document_admin_search_combined_fields(admin_client):
    """Test that DocumentAdmin search works when combining engagements__num_ej with other fields"""
    # Create test engagement
    engagement = DataEngagementFactory(num_ej="EJ_SEARCH")

    # Create documents
    doc1 = DocumentFactory(filename="searchable_document.pdf")
    doc1.engagements.add(engagement)

    doc2 = DocumentFactory(filename="other_document.pdf")
    doc2.engagements.add(engagement)

    # Test search for both filename and engagement
    list_url = reverse("admin:docia_document_changelist")
    search_url = f"{list_url}?q=searchable+EJ_SEARCH"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Should find doc1 (matches both criteria)
    assert "searchable_document.pdf" in str(response.content)

    # doc2 should not appear because it doesn't match the filename search
    assert "other_document.pdf" not in str(response.content)


@pytest.mark.django_db
def test_document_admin_list_view_shows_engagements(admin_client):
    """Test that the document list view in admin shows documents with their engagements"""
    # Create test engagement
    engagement = DataEngagementFactory(num_ej="EJ_LIST_TEST")

    # Create document with engagement
    doc = DocumentFactory(filename="list_test_document.pdf")
    doc.engagements.add(engagement)

    # Get the document list URL
    list_url = reverse("admin:docia_document_changelist")

    # Test GET request
    response = admin_client.get(list_url)
    assert response.status_code == 200

    # Check that the document appears in the list
    assert "list_test_document.pdf" in str(response.content)


@pytest.mark.django_db
def test_document_admin_search_empty_query(admin_client):
    """Test that DocumentAdmin search with empty query returns all documents"""
    # Create test engagements
    engagement1 = DataEngagementFactory(num_ej="EJ_EMPTY1")
    engagement2 = DataEngagementFactory(num_ej="EJ_EMPTY2")

    # Create documents
    doc1 = DocumentFactory(filename="empty_search_doc1.pdf")
    doc1.engagements.add(engagement1)

    doc2 = DocumentFactory(filename="empty_search_doc2.pdf")
    doc2.engagements.add(engagement2)

    # Test empty search (should return all documents)
    list_url = reverse("admin:docia_document_changelist")
    search_url = f"{list_url}?q="
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Both documents should appear
    assert "empty_search_doc1.pdf" in str(response.content)
    assert "empty_search_doc2.pdf" in str(response.content)
