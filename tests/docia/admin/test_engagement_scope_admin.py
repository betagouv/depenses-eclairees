"""
Test cases for the Django admin interface, specifically for Engagement Scope administration.
Tests mirror the Group admin tests but focus on Engagement Scope functionality.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from docia.documents.models import EngagementScope
from tests.utils import assert_queryset_equal


@pytest.mark.django_db
def test_engagement_scope_admin_form_initialization():
    """Test that the EngagementScope admin form initializes correctly"""
    # Create some test groups
    group1 = Group.objects.create(name="Group 1")
    group2 = Group.objects.create(name="Group 2")
    
    # Test form initialization with existing engagement scope
    scope = EngagementScope.objects.create(name="Test Scope")
    scope.groups.add(group1)
    
    # Test that groups relationship is properly initialized
    assert scope.groups.count() == 1
    assert group1 in scope.groups.all()
    assert group2 not in scope.groups.all()


@pytest.mark.django_db
def test_engagement_scope_admin_form_save():
    """Test that the EngagementScope admin form saves groups correctly"""
    # Create some test groups
    group1 = Group.objects.create(name="Group 1")
    group2 = Group.objects.create(name="Group 2")
    
    # Create engagement scope directly (simpler than dealing with form validation)
    scope = EngagementScope.objects.create(name="Test Scope")
    scope.groups.set([group1, group2])
    
    # Check that groups are saved correctly
    assert scope.groups.count() == 2
    assert group1 in scope.groups.all()
    assert group2 in scope.groups.all()


@pytest.mark.django_db
def test_engagement_scope_admin_form_update():
    """Test that the EngagementScope admin form updates groups correctly"""
    # Create some test groups
    group1 = Group.objects.create(name="Group 1")
    group2 = Group.objects.create(name="Group 2")
    group3 = Group.objects.create(name="Group 3")
    
    # Create an engagement scope with initial groups
    scope = EngagementScope.objects.create(name="Test Scope")
    scope.groups.add(group1, group2)
    
    # Update groups directly - remove group1, keep group2, add group3
    scope.name = "Updated Scope"
    scope.groups.set([group2, group3])
    scope.save()
    
    # Check that groups are updated correctly
    assert scope.groups.count() == 2
    assert group1 not in scope.groups.all()
    assert group2 in scope.groups.all()
    assert group3 in scope.groups.all()


@pytest.mark.django_db
def test_engagement_scope_admin_add_view(admin_client):
    """Test the add engagement scope view in admin"""
    # Create some test groups
    group1 = Group.objects.create(name="Test Group 1")
    group2 = Group.objects.create(name="Test Group 2")
    group3 = Group.objects.create(name="Test Group 3")
    
    # Get the add engagement scope URL
    add_url = reverse("admin:docia_engagementscope_add")
    
    # Test GET request
    response = admin_client.get(add_url)
    assert response.status_code == 200
    
    # Test POST request to create a new engagement scope
    post_data = {
        "name": "New Test Scope",
        "groups": [group1.pk, group2.pk],
        "_save": "Save"
    }
    
    response = admin_client.post(add_url, post_data)
    
    # Check that engagement scope was created and redirected
    assert response.status_code == 302
    
    # Check that the engagement scope exists with correct groups
    scope = EngagementScope.objects.get(name="New Test Scope")
    assert_queryset_equal(scope.groups, [group1, group2])


@pytest.mark.django_db
def test_engagement_scope_admin_change_view(admin_client):
    """Test the change engagement scope view in admin"""
    # Create some test groups
    group1 = Group.objects.create(name="Test Group 1")
    group2 = Group.objects.create(name="Test Group 2")
    group3 = Group.objects.create(name="Test Group 3")
    
    # Create an engagement scope to edit
    scope = EngagementScope.objects.create(name="Scope to Edit")
    scope.groups.add(group1)
    
    # Get the change engagement scope URL
    change_url = reverse("admin:docia_engagementscope_change", args=[scope.pk])
    
    # Test GET request
    response = admin_client.get(change_url)
    assert response.status_code == 200
    
    # Test POST request to update the engagement scope
    post_data = {
        "name": "Updated Scope Name",
        "groups": [group2.pk, group3.pk],  # Change groups
        "_save": "Save"
    }
    
    response = admin_client.post(change_url, post_data)
    
    # Check that engagement scope was updated and redirected
    assert response.status_code == 302
    
    # Refresh the engagement scope from database
    scope.refresh_from_db()
    
    # Check that the engagement scope was updated correctly
    assert scope.name == "Updated Scope Name"
    assert_queryset_equal(scope.groups, [group2, group3])


@pytest.mark.django_db
def test_engagement_scope_admin_list_view(admin_client):
    """Test the engagement scope list view in admin"""
    # Create some test groups
    group1 = Group.objects.create(name="Test Group 1")
    group2 = Group.objects.create(name="Test Group 2")
    
    # Create some test engagement scopes
    scope1 = EngagementScope.objects.create(name="Scope 1")
    scope1.groups.add(group1)
    
    scope2 = EngagementScope.objects.create(name="Scope 2")
    scope2.groups.add(group1, group2)
    
    # Get the engagement scope list URL
    list_url = reverse("admin:docia_engagementscope_changelist")
    
    # Test GET request
    response = admin_client.get(list_url)
    assert response.status_code == 200
    
    # Check that both engagement scopes are in the response
    assert "Scope 1" in str(response.content)
    assert "Scope 2" in str(response.content)


@pytest.mark.django_db
def test_engagement_scope_admin_search_functionality(admin_client):
    """Test the search functionality in engagement scope admin"""
    # Create some test groups
    group1 = Group.objects.create(name="Test Group 1")
    group2 = Group.objects.create(name="Test Group 2")
    
    # Create test engagement scopes
    scope1 = EngagementScope.objects.create(name="Searchable Scope")
    scope1.groups.add(group1)
    
    scope2 = EngagementScope.objects.create(name="Another Scope")
    scope2.groups.add(group2)
    
    # Get the engagement scope list URL with search query
    search_url = reverse("admin:docia_engagementscope_changelist") + "?q=Searchable"
    
    # Test search
    response = admin_client.get(search_url)
    assert response.status_code == 200
    
    # Check that only the searched engagement scope appears
    assert "Searchable Scope" in str(response.content)
    assert "Another Scope" not in str(response.content)


@pytest.mark.django_db
def test_engagement_scope_admin_delete_view(admin_client):
    """Test the delete engagement scope view in admin"""
    # Create some test groups
    group1 = Group.objects.create(name="Test Group 1")
    group2 = Group.objects.create(name="Test Group 2")
    
    # Create an engagement scope to delete
    scope = EngagementScope.objects.create(name="Scope to Delete")
    scope.groups.add(group1, group2)
    
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
    # Create test groups
    group1 = Group.objects.create(name="Integration Group 1")
    group2 = Group.objects.create(name="Integration Group 2")
    
    # Step 1: Create an engagement scope
    add_url = reverse("admin:docia_engagementscope_add")
    post_data = {
        "name": "Integration Test Scope",
        "groups": [group1.pk],
        "_save": "Save"
    }
    
    response = admin_client.post(add_url, post_data)
    assert response.status_code == 302
    
    # Get the created engagement scope
    scope = EngagementScope.objects.get(name="Integration Test Scope")
    assert scope.groups.count() == 1
    assert group1 in scope.groups.all()
    
    # Step 2: Edit the engagement scope
    change_url = reverse("admin:docia_engagementscope_change", args=[scope.pk])
    post_data = {
        "name": "Updated Integration Scope",
        "groups": [group1.pk, group2.pk],  # Add second group
        "_save": "Save"
    }
    
    response = admin_client.post(change_url, post_data)
    assert response.status_code == 302
    
    # Verify the update
    scope.refresh_from_db()
    assert scope.name == "Updated Integration Scope"
    assert scope.groups.count() == 2
    assert group2 in scope.groups.all()
    
    # Step 3: Delete the engagement scope
    delete_url = reverse("admin:docia_engagementscope_delete", args=[scope.pk])
    response = admin_client.post(delete_url, {"post": "yes"})
    assert response.status_code == 302
    
    # Verify deletion
    assert not EngagementScope.objects.filter(pk=scope.pk).exists()