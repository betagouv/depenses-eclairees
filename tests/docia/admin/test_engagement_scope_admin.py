"""
Test cases for the Django admin interface, specifically for Engagement Scope administration.
Tests mirror the Group admin tests but focus on Engagement Scope functionality.
"""

from django.urls import reverse

import pytest

from docia.documents.models import EngagementScope


@pytest.mark.django_db
def test_engagement_scope_admin_add_view(admin_client):
    """Test the add engagement scope view in admin"""
    # Get the add engagement scope URL
    add_url = reverse("admin:docia_engagementscope_add")

    # Test GET request
    response = admin_client.get(add_url)
    assert response.status_code == 200

    # Test POST request to create a new engagement scope
    post_data = {
        "purchase_organization": "NewOA",
        "purchase_group": "NewGA",
        "_save": "Save",
    }

    response = admin_client.post(add_url, post_data)

    # Check that engagement scope was created and redirected
    assert response.status_code == 302

    # Check that the engagement scope exists with correct fields
    scope = EngagementScope.objects.get(purchase_organization="NewOA", purchase_group="NewGA")
    assert scope.purchase_organization == "NewOA"
    assert scope.purchase_group == "NewGA"


@pytest.mark.django_db
def test_engagement_scope_admin_change_view(admin_client):
    """Test the change engagement scope view in admin"""
    # Create an engagement scope to edit
    scope = EngagementScope.objects.create(purchase_organization="OAtoEdit", purchase_group="GAtoEdit")

    # Get the change engagement scope URL
    change_url = reverse("admin:docia_engagementscope_change", args=[scope.pk])

    # Test GET request
    response = admin_client.get(change_url)
    assert response.status_code == 200

    # Test POST request to update the engagement scope
    post_data = {
        "purchase_organization": "UpdatedOA",
        "purchase_group": "UpdatedGA",
        "_save": "Save",
    }

    response = admin_client.post(change_url, post_data)

    # Check that engagement scope was updated and redirected
    assert response.status_code == 302

    # Refresh the engagement scope from database
    scope.refresh_from_db()

    # Check that the engagement scope was updated correctly
    assert scope.purchase_organization == "UpdatedOA"
    assert scope.purchase_group == "UpdatedGA"


@pytest.mark.django_db
def test_engagement_scope_admin_list_view(admin_client):
    """Test the engagement scope list view in admin"""
    # Create some test engagement scopes
    scope1 = EngagementScope.objects.create(purchase_organization="OA1", purchase_group="GA1")
    scope2 = EngagementScope.objects.create(purchase_organization="OA2", purchase_group="GA2")

    # Get the engagement scope list URL
    list_url = reverse("admin:docia_engagementscope_changelist")

    # Test GET request
    response = admin_client.get(list_url)
    assert response.status_code == 200

    # Check that both engagement scopes are in the response
    assert scope1.purchase_organization in response.text
    assert scope2.purchase_organization in response.text


@pytest.mark.django_db
def test_engagement_scope_admin_search_functionality(admin_client):
    """Test the search functionality in engagement scope admin"""
    # Create test engagement scopes
    searchable = EngagementScope.objects.create(purchase_organization="SearchableOA", purchase_group="GA1")
    other = EngagementScope.objects.create(purchase_organization="AnotherOA", purchase_group="GA2")

    # Get the engagement scope list URL with search query
    search_url = reverse("admin:docia_engagementscope_changelist") + "?q=Searchable"

    # Test search
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that only the searched engagement scope appears
    assert searchable.purchase_organization in response.text
    assert other.purchase_organization not in response.text


@pytest.mark.django_db
def test_engagement_scope_admin_delete_view(admin_client):
    """Test the delete engagement scope view in admin"""
    # Create an engagement scope to delete
    scope = EngagementScope.objects.create(purchase_organization="OAtoDelete", purchase_group="GAtoDelete")

    scope_id = scope.pk

    # Get the delete engagement scope URL
    delete_url = reverse("admin:docia_engagementscope_delete", args=[scope.pk])

    # Test GET request (confirmation page)
    response = admin_client.get(delete_url)
    assert response.status_code == 200

    # Test POST request to actually delete
    response = admin_client.post(delete_url, {"post": "yes"})

    # Check that engagement scope was deleted and redirected
    assert response.status_code == 302

    # Check that the engagement scope no longer exists
    assert not EngagementScope.objects.filter(pk=scope_id).exists()


@pytest.mark.django_db
def test_complete_engagement_scope_lifecycle(admin_client):
    """Test the complete lifecycle of an engagement scope in admin: create, edit, delete"""
    # Step 1: Create an engagement scope
    add_url = reverse("admin:docia_engagementscope_add")
    post_data = {
        "purchase_organization": "IntegrationOA",
        "purchase_group": "IntegrationGA",
        "_save": "Save",
    }

    response = admin_client.post(add_url, post_data)
    assert response.status_code == 302

    # Get the created engagement scope
    scope = EngagementScope.objects.get(purchase_organization="IntegrationOA", purchase_group="IntegrationGA")
    assert scope.purchase_organization == "IntegrationOA"
    assert scope.purchase_group == "IntegrationGA"

    # Step 2: Edit the engagement scope
    change_url = reverse("admin:docia_engagementscope_change", args=[scope.pk])
    post_data = {
        "purchase_organization": "UpdatedIntegrationOA",
        "purchase_group": "UpdatedIntegrationGA",
        "_save": "Save",
    }

    response = admin_client.post(change_url, post_data)
    assert response.status_code == 302

    # Verify the update
    scope.refresh_from_db()
    assert scope.purchase_organization == "UpdatedIntegrationOA"
    assert scope.purchase_group == "UpdatedIntegrationGA"

    # Step 3: Delete the engagement scope
    delete_url = reverse("admin:docia_engagementscope_delete", args=[scope.pk])
    response = admin_client.post(delete_url, {"post": "yes"})
    assert response.status_code == 302

    # Verify deletion
    assert not EngagementScope.objects.filter(pk=scope.pk).exists()
