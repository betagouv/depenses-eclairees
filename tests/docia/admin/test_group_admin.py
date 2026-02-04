"""
Test cases for the Django admin interface, specifically for Group administration.
Tests the add/edit functionality of groups with scopes.
"""

from django.contrib.auth.models import Group
from django.urls import reverse

import pytest

from docia.admin import AdminGroupForm
from docia.documents.models import EngagementScope
from tests.utils import assert_queryset_equal


@pytest.mark.django_db
def test_group_admin_form_initialization():
    """Test that the AdminGroupForm initializes correctly"""
    # Create some test scopes
    scope1 = EngagementScope.objects.create(name="Scope 1")
    scope2 = EngagementScope.objects.create(name="Scope 2")

    # Test form initialization with existing group
    group = Group.objects.create(name="Test Group")
    group.scopes.add(scope1)

    form = AdminGroupForm(instance=group)

    # Check that scopes field is properly initialized
    assert "scopes" in form.fields
    assert scope1 in form.fields["scopes"].initial
    assert scope2 not in form.fields["scopes"].initial


@pytest.mark.django_db
def test_group_admin_form_save():
    """Test that the AdminGroupForm saves scopes correctly"""
    # Create some test scopes
    scope1 = EngagementScope.objects.create(name="Scope 1")
    scope2 = EngagementScope.objects.create(name="Scope 2")

    # Create form data
    form_data = {"name": "Test Group", "permissions": [], "scopes": [scope1.pk, scope2.pk]}

    form = AdminGroupForm(data=form_data)
    assert form.is_valid()

    # Save the form
    group = form.save()

    # Check that scopes are saved correctly
    assert group.scopes.count() == 2
    assert scope1 in group.scopes.all()
    assert scope2 in group.scopes.all()


@pytest.mark.django_db
def test_group_admin_form_update():
    """Test that the AdminGroupForm updates scopes correctly"""
    # Create some test scopes
    scope1 = EngagementScope.objects.create(name="Scope 1")
    scope2 = EngagementScope.objects.create(name="Scope 2")
    scope3 = EngagementScope.objects.create(name="Scope 3")

    # Create a group with initial scopes
    group = Group.objects.create(name="Test Group")
    group.scopes.add(scope1, scope2)

    # Update form data - remove scope1, keep scope2, add scope3
    form_data = {"name": "Updated Group", "permissions": [], "scopes": [scope2.pk, scope3.pk]}

    form = AdminGroupForm(data=form_data, instance=group)
    assert form.is_valid()

    # Save the form
    updated_group = form.save()

    # Check that scopes are updated correctly
    assert updated_group.scopes.count() == 2
    assert scope1 not in updated_group.scopes.all()
    assert scope2 in updated_group.scopes.all()
    assert scope3 in updated_group.scopes.all()


@pytest.mark.django_db
def test_group_admin_add_view(admin_client):
    """Test the add group view in admin"""
    # Create some test scopes
    scope1 = EngagementScope.objects.create(name="Test Scope 1")
    scope2 = EngagementScope.objects.create(name="Test Scope 2")
    # This one should not be added
    EngagementScope.objects.create(name="Test Scope 3")

    # Get the add group URL
    add_url = reverse("admin:auth_group_add")

    # Test GET request
    response = admin_client.get(add_url)
    assert response.status_code == 200

    # Test POST request to create a new group
    post_data = {"name": "New Test Group", "permissions": [], "scopes": [scope1.pk, scope2.pk], "_save": "Save"}

    response = admin_client.post(add_url, post_data)

    # Check that group was created and redirected
    assert response.status_code == 302

    # Check that the group exists with correct scopes
    group = Group.objects.get(name="New Test Group")
    assert_queryset_equal(group.scopes, [scope1, scope2])


@pytest.mark.django_db
def test_group_admin_change_view(admin_client):
    """Test the change group view in admin"""
    # Create some test scopes
    scope1 = EngagementScope.objects.create(name="Test Scope 1")
    scope2 = EngagementScope.objects.create(name="Test Scope 2")
    scope3 = EngagementScope.objects.create(name="Test Scope 3")

    # Create a group to edit
    group = Group.objects.create(name="Group to Edit")
    group.scopes.add(scope1)

    # Get the change group URL
    change_url = reverse("admin:auth_group_change", args=[group.pk])

    # Test GET request
    response = admin_client.get(change_url)
    assert response.status_code == 200

    # Test POST request to update the group
    post_data = {
        "name": "Updated Group Name",
        "permissions": [],
        "scopes": [scope2.pk, scope3.pk],  # Change scopes
        "_save": "Save",
    }

    response = admin_client.post(change_url, post_data)

    # Check that group was updated and redirected
    assert response.status_code == 302

    # Refresh the group from database
    group.refresh_from_db()

    # Check that the group was updated correctly
    assert group.name == "Updated Group Name"
    assert_queryset_equal(group.scopes, [scope2, scope3])


@pytest.mark.django_db
def test_group_admin_list_view(admin_client):
    """Test the group list view in admin"""
    # Create some test scopes
    scope1 = EngagementScope.objects.create(name="Test Scope 1")
    scope2 = EngagementScope.objects.create(name="Test Scope 2")

    # Create some test groups
    group1 = Group.objects.create(name="Group 1")
    group1.scopes.add(scope1)

    group2 = Group.objects.create(name="Group 2")
    group2.scopes.add(scope1, scope2)

    # Get the group list URL
    list_url = reverse("admin:auth_group_changelist")

    # Test GET request
    response = admin_client.get(list_url)
    assert response.status_code == 200

    # Check that both groups are in the response
    assert "Group 1" in str(response.content)
    assert "Group 2" in str(response.content)


@pytest.mark.django_db
def test_group_admin_search_functionality(admin_client):
    """Test the search functionality in group admin"""
    # Create some test scopes
    scope1 = EngagementScope.objects.create(name="Test Scope 1")
    scope2 = EngagementScope.objects.create(name="Test Scope 2")

    # Create test groups
    group1 = Group.objects.create(name="Searchable Group")
    group1.scopes.add(scope1)

    group2 = Group.objects.create(name="Another Group")
    group2.scopes.add(scope2)

    # Get the group list URL with search query
    search_url = reverse("admin:auth_group_changelist") + "?q=Searchable"

    # Test search
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that only the searched group appears
    assert "Searchable Group" in str(response.content)
    assert "Another Group" not in str(response.content)


@pytest.mark.django_db
def test_complete_group_lifecycle(admin_client):
    """Test the complete lifecycle of a group in admin: create, edit, delete"""
    # Create test scopes
    scope1 = EngagementScope.objects.create(name="Integration Scope 1")
    scope2 = EngagementScope.objects.create(name="Integration Scope 2")

    # Step 1: Create a group
    add_url = reverse("admin:auth_group_add")
    post_data = {"name": "Integration Test Group", "permissions": [], "scopes": [scope1.pk], "_save": "Save"}

    response = admin_client.post(add_url, post_data)
    assert response.status_code == 302

    # Get the created group
    group = Group.objects.get(name="Integration Test Group")
    assert group.scopes.count() == 1
    assert scope1 in group.scopes.all()

    # Step 2: Edit the group
    change_url = reverse("admin:auth_group_change", args=[group.pk])
    post_data = {
        "name": "Updated Integration Group",
        "permissions": [],
        "scopes": [scope1.pk, scope2.pk],  # Add second scope
        "_save": "Save",
    }

    response = admin_client.post(change_url, post_data)
    assert response.status_code == 302

    # Verify the update
    group.refresh_from_db()
    assert group.name == "Updated Integration Group"
    assert group.scopes.count() == 2
    assert scope2 in group.scopes.all()

    # Step 3: Delete the group
    delete_url = reverse("admin:auth_group_delete", args=[group.pk])
    response = admin_client.post(delete_url, {"post": "yes"})
    assert response.status_code == 302

    # Verify deletion
    assert not Group.objects.filter(pk=group.pk).exists()
