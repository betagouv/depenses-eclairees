"""
Test cases for the Django admin interface, specifically for Engagement administration.
Tests the add/edit functionality of Engagements with EngagementScope linking.
"""

from django.urls import reverse

import pytest

from docia.documents.models import Engagement, EngagementScope
from tests.factories.data import EngagementFactory
from tests.utils import assert_queryset_equal


@pytest.mark.django_db
def test_engagement_admin_add_view(admin_client):
    """Test the add Engagement view in admin"""
    # Create some EngagementScopes first
    scope1 = EngagementScope.objects.create(purchase_organization="OA1", purchase_group="GA1")
    scope2 = EngagementScope.objects.create(purchase_organization="OA2", purchase_group="GA2")

    # Get the add Engagement URL
    add_url = reverse("admin:docia_engagement_add")

    # Test GET request
    response = admin_client.get(add_url)
    assert response.status_code == 200

    # Test POST request to create a new Engagement with linked scopes
    post_data = {
        "num_ej": "EJ001",
        "scopes": [str(scope1.id), str(scope2.id)],
        "_save": "Save",
    }

    response = admin_client.post(add_url, post_data)

    # Check that Engagement was created and redirected
    assert response.status_code == 302

    # Check that the Engagement exists with correct scopes
    engagement = Engagement.objects.get(num_ej="EJ001")
    assert_queryset_equal(engagement.scopes.all(), [scope1, scope2])


@pytest.mark.django_db
def test_engagement_admin_change_view(admin_client):
    """Test the change Engagement view in admin"""
    # Create EngagementScopes
    scope1 = EngagementScope.objects.create(purchase_organization="OA1", purchase_group="GA1")
    scope2 = EngagementScope.objects.create(purchase_organization="OA2", purchase_group="GA2")
    scope3 = EngagementScope.objects.create(purchase_organization="OA3", purchase_group="GA3")

    # Create a Engagement to edit with initial scope
    engagement = Engagement.objects.create(num_ej="EJ002")
    engagement.scopes.add(scope1)

    # Get the change Engagement URL
    change_url = reverse("admin:docia_engagement_change", args=[engagement.pk])

    # Test GET request
    response = admin_client.get(change_url)
    assert response.status_code == 200

    # Test POST request to update the Engagement num_ej and its scopes
    post_data = {
        "num_ej": "EJ_UPDATED",  # Changed from EJ002 to EJ_UPDATED
        "scopes": [str(scope2.id), str(scope3.id)],
        "_save": "Save",
    }

    response = admin_client.post(change_url, post_data)

    # Check that Engagement was updated and redirected
    assert response.status_code == 302

    # Refresh the Engagement from database
    engagement.refresh_from_db()

    # Check that the Engagement num_ej and scopes were updated correctly
    assert engagement.num_ej == "EJ_UPDATED"
    assert_queryset_equal(engagement.scopes.all(), [scope2, scope3])


@pytest.mark.django_db
def test_engagement_admin_list_view(admin_client):
    """Test the Engagement list view in admin"""
    # Create EngagementScopes
    scope1 = EngagementScope.objects.create(purchase_organization="OA1", purchase_group="GA1")
    scope2 = EngagementScope.objects.create(purchase_organization="OA2", purchase_group="GA2")

    # Create some test Engagements
    engagement1 = Engagement.objects.create(num_ej="EJ003")
    engagement1.scopes.add(scope1)

    engagement2 = Engagement.objects.create(num_ej="EJ004")
    engagement2.scopes.add(scope1)
    engagement2.scopes.add(scope2)

    # Get the Engagement list URL
    list_url = reverse("admin:docia_engagement_changelist")

    # Test GET request
    response = admin_client.get(list_url)
    assert response.status_code == 200

    # Check that both Engagements are in the response
    assert "EJ003" in response.text
    assert "EJ004" in response.text
    # Check that scopes are displayed
    assert "OA1/GA1" in response.text
    assert "OA2/GA2" in response.text


@pytest.mark.django_db
def test_engagement_admin_search_functionality(admin_client):
    """Test the search functionality in Engagement admin"""
    # Create EngagementScopes
    scope1 = EngagementScope.objects.create(purchase_organization="OA1", purchase_group="GA1")
    scope2 = EngagementScope.objects.create(purchase_organization="SEARCH_OA", purchase_group="SEARCH_GA")

    # Create test Engagements
    engagement1 = Engagement.objects.create(num_ej="EJ_SEARCH")
    engagement1.scopes.add(scope1)

    engagement2 = Engagement.objects.create(num_ej="EJ_OTHER")
    engagement2.scopes.add(scope2)

    # Test 1: Search by num_ej
    search_url = reverse("admin:docia_engagement_changelist") + "?q=EJ_SEARCH"
    response = admin_client.get(search_url)
    assert response.status_code == 200
    assert "EJ_SEARCH" in response.text
    assert "EJ_OTHER" not in response.text

    # Test 2: Search by purchase_organization
    search_url = reverse("admin:docia_engagement_changelist") + "?q=SEARCH_OA"
    response = admin_client.get(search_url)
    assert response.status_code == 200
    assert "EJ_OTHER" in response.text
    assert "EJ_SEARCH" not in response.text

    # Test 3: Search by purchase_group
    search_url = reverse("admin:docia_engagement_changelist") + "?q=SEARCH_GA"
    response = admin_client.get(search_url)
    assert response.status_code == 200
    assert "EJ_OTHER" in response.text
    assert "EJ_SEARCH" not in response.text


@pytest.mark.django_db
def test_engagement_admin_scopes_display(admin_client):
    """Test that the scopes are displayed correctly in the list view"""
    # Create EngagementScopes
    scope1 = EngagementScope.objects.create(purchase_organization="OA1", purchase_group="GA1")
    scope2 = EngagementScope.objects.create(purchase_organization="OA2", purchase_group="GA2")
    scope3 = EngagementScope.objects.create(purchase_organization="OA3", purchase_group="GA3")

    # Create Engagement with multiple scopes
    engagement = Engagement.objects.create(num_ej="EJ_MULTI")
    engagement.scopes.add(scope1, scope2, scope3)

    # Get the Engagement list URL
    list_url = reverse("admin:docia_engagement_changelist")

    # Test GET request
    response = admin_client.get(list_url)
    assert response.status_code == 200

    # Check that the scopes are displayed as comma-separated values
    # The scopes should appear in the format "OA1/GA1, OA2/GA2, OA3/GA3"
    assert "OA1/GA1, OA2/GA2, OA3/GA3" in response.text


@pytest.mark.django_db
def test_complete_engagement_lifecycle(admin_client):
    """Test the complete lifecycle of a Engagement in admin: create, edit, delete"""
    # Create EngagementScopes
    scope1 = EngagementScope.objects.create(purchase_organization="OA1", purchase_group="GA1")
    scope2 = EngagementScope.objects.create(purchase_organization="OA2", purchase_group="GA2")

    # Step 1: Create a Engagement with scopes
    add_url = reverse("admin:docia_engagement_add")
    post_data = {
        "num_ej": "EJ_LIFECYCLE",
        "scopes": [str(scope1.id)],
        "_save": "Save",
    }

    response = admin_client.post(add_url, post_data)
    assert response.status_code == 302

    # Get the created Engagement and verify scopes
    engagement = Engagement.objects.get(num_ej="EJ_LIFECYCLE")
    assert_queryset_equal(engagement.scopes.all(), [scope1])

    # Step 2: Edit the Engagement and change num_ej and scopes
    change_url = reverse("admin:docia_engagement_change", args=[engagement.pk])
    post_data = {
        "num_ej": "EJ_LIFECYCLE_UPDATED",  # Changed from EJ_LIFECYCLE to EJ_LIFECYCLE_UPDATED
        "scopes": [str(scope1.id), str(scope2.id)],
        "_save": "Save",
    }

    response = admin_client.post(change_url, post_data)
    assert response.status_code == 302

    # Verify the update
    engagement.refresh_from_db()
    assert engagement.num_ej == "EJ_LIFECYCLE_UPDATED"
    assert_queryset_equal(engagement.scopes.all(), [scope1, scope2])

    # Step 3: Delete the Engagement
    delete_url = reverse("admin:docia_engagement_delete", args=[engagement.pk])
    response = admin_client.post(delete_url, {"post": "yes"})
    assert response.status_code == 302

    # Verify deletion
    assert not Engagement.objects.filter(pk=engagement.pk).exists()


@pytest.mark.django_db
def test_engagement_admin_export_action(admin_client):
    """Test the export_as_json admin action with two engagements"""
    import json

    from tests.factories.data import DocumentFactory, EngagementScopeFactory

    # Create scopes
    scope1 = EngagementScopeFactory()
    scope2 = EngagementScopeFactory()

    # Create two engagements with scopes and documents
    engagement1 = EngagementFactory(num_ej="EJ_EXPORT_1")
    engagement1.scopes.add(scope1)
    doc1 = DocumentFactory()
    doc1.engagements.add(engagement1)

    engagement2 = EngagementFactory(num_ej="EJ_EXPORT_2")
    engagement2.scopes.add(scope2)
    doc2 = DocumentFactory()
    doc2.engagements.add(engagement2)

    # Get the engagement list URL with export action
    list_url = reverse("admin:docia_engagement_changelist")

    # Post to the export action with both engagements selected
    response = admin_client.post(
        list_url,
        {
            "action": "export_as_json",
            "_selected_action": [str(engagement1.pk), str(engagement2.pk)],
        },
    )

    # Check response is successful
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert "attachment" in response["Content-Disposition"]

    # Parse JSON content
    content = json.loads(response.content)

    # Check that both num_ej are present in the JSON
    assert "engagements" in content
    num_ejs = [e["num_ej"] for e in content["engagements"]]
    assert "EJ_EXPORT_1" in num_ejs
    assert "EJ_EXPORT_2" in num_ejs
