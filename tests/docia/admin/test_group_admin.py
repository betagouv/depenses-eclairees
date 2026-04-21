"""
Test cases for the Django admin interface, specifically for Group administration.
Tests the add/edit functionality of groups with GroupScope inline editing.
"""

from django.contrib.auth.models import Group
from django.urls import reverse

import pytest

from docia.permissions.models import GroupScope


def _build_scope_payload(scopes, initials=None):
    initials = initials or []
    payload: dict[str, str] = {
        "scope_set-TOTAL_FORMS": str(len(scopes) + len(initials)),
        "scope_set-INITIAL_FORMS": str(len(initials)),
    }
    offset = 0
    for i, scope in enumerate(initials, start=offset):
        payload[f"scope_set-{i}-id"] = str(scope["id"])
        if scope.get("delete"):
            payload[f"scope_set-{i}-DELETE"] = "on"
        else:
            payload[f"scope_set-{i}-purchase_organization"] = scope["purchase_organization"]
            payload[f"scope_set-{i}-purchase_group"] = scope["purchase_group"]
    offset += len(initials)
    for i, (org, group) in enumerate(scopes, start=offset):
        payload[f"scope_set-{i}-purchase_organization"] = org
        payload[f"scope_set-{i}-purchase_group"] = group
    return payload


@pytest.mark.django_db
def test_group_admin_add_view(admin_client):
    """Test the add group view in admin with GroupScope inline editing"""
    # Get the add group URL
    add_url = reverse("admin:auth_group_add")

    # Test GET request
    response = admin_client.get(add_url)
    assert response.status_code == 200

    # Test POST request to create a new group with inline GroupScopes
    scopes = [("OA1", "GA1"), ("OA2", "GA2")]
    post_data = {
        "name": "New Test Group",
        **_build_scope_payload(scopes),
    }

    response = admin_client.post(add_url, post_data)

    # Check that group was created and redirected
    assert response.status_code == 302

    # Check that the group exists and has correct GroupScopes
    group = Group.objects.get(name="New Test Group")
    db_scopes = sorted(group.scope_set.values_list("purchase_organization", "purchase_group"))
    assert db_scopes == scopes


@pytest.mark.django_db
def test_group_admin_change_view(admin_client):
    """Test the change group view in admin with GroupScope inline editing"""
    # Create a group to edit
    group = Group.objects.create(name="Group to Edit")
    # Create initial GroupScope
    scope = GroupScope.objects.create(group=group, purchase_organization="OA1", purchase_group="GA1")

    # Get the change group URL
    change_url = reverse("admin:auth_group_change", args=[group.pk])

    # Test GET request
    response = admin_client.get(change_url)
    assert response.status_code == 200

    # Test POST request to update the group and its GroupScopes
    scopes = [("OA2", "GA2"), ("OA3", "GA3")]
    initials = [{"id": scope.id, "delete": True}]
    post_data = {
        "name": "Updated Group Name",
        **_build_scope_payload(scopes, initials=initials),
    }

    response = admin_client.post(change_url, post_data)

    # Check that group was updated and redirected
    assert response.status_code == 302

    # Refresh the group from database
    group.refresh_from_db()

    # Check that the group was updated correctly
    assert group.name == "Updated Group Name"
    db_scopes = sorted(group.scope_set.values_list("purchase_organization", "purchase_group"))
    assert db_scopes == scopes


@pytest.mark.django_db
def test_group_admin_list_view(admin_client):
    """Test the group list view in admin"""
    # Create some test groups with GroupScopes
    group1 = Group.objects.create(name="Group 1")
    GroupScope.objects.create(group=group1, purchase_organization="OA1", purchase_group="GA1")

    group2 = Group.objects.create(name="Group 2")
    GroupScope.objects.create(group=group2, purchase_organization="OA2", purchase_group="GA2")
    GroupScope.objects.create(group=group2, purchase_organization="OA3", purchase_group="GA3")

    # Get the group list URL
    list_url = reverse("admin:auth_group_changelist")

    # Test GET request
    response = admin_client.get(list_url)
    assert response.status_code == 200

    # Check that both groups are in the response
    assert "Group 1" in response.text
    assert "Group 2" in response.text
    assert "OA1/GA1" in response.text
    assert "OA2/GA2" in response.text
    assert "OA3/GA3" in response.text


@pytest.mark.django_db
def test_group_admin_search_functionality(admin_client):
    """Test the search functionality in group admin"""
    # Create test groups
    group1 = Group.objects.create(name="Searchable Group")
    GroupScope.objects.create(group=group1, purchase_organization="OA1", purchase_group="GA1")

    group2 = Group.objects.create(name="Another Group")
    GroupScope.objects.create(group=group2, purchase_organization="OA2", purchase_group="GA2")

    # Get the group list URL with search query
    search_url = reverse("admin:auth_group_changelist") + "?q=Searchable"

    # Test search
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that only the searched group appears
    assert "Searchable Group" in response.text
    assert "Another Group" not in response.text


@pytest.mark.django_db
def test_complete_group_lifecycle(admin_client):
    """Test the complete lifecycle of a group in admin: create, edit, delete"""
    # Step 1: Create a group with GroupScopes
    add_url = reverse("admin:auth_group_add")
    scopes = [("OA1", "GA1"), ("OA1", "GA2")]
    post_data = {
        "name": "Integration Test Group",
        **_build_scope_payload(scopes),
    }

    response = admin_client.post(add_url, post_data)
    assert response.status_code == 302

    # Get the created group and verify GroupScopes
    group = Group.objects.get(name="Integration Test Group")
    db_scopes = sorted(group.scope_set.values_list("purchase_organization", "purchase_group"))
    assert db_scopes == scopes

    # Step 2: Edit the group and add more GroupScopes
    change_url = reverse("admin:auth_group_change", args=[group.pk])
    new_scopes = [("OA2", "GA2")]
    initials = list(
        group.scope_set.order_by("purchase_organization", "purchase_group").values(
            "id", "purchase_organization", "purchase_group"
        )
    )
    initials[1]["delete"] = True
    post_data = {
        "name": "Updated Integration Group",
        **_build_scope_payload(new_scopes, initials=initials),
    }

    response = admin_client.post(change_url, post_data)
    assert response.status_code == 302

    # Verify the update
    group.refresh_from_db()
    assert group.name == "Updated Integration Group"
    scopes = [("OA1", "GA1"), ("OA2", "GA2")]
    db_scopes = sorted(group.scope_set.values_list("purchase_organization", "purchase_group"))
    assert db_scopes == scopes

    # Step 3: Delete the group
    delete_url = reverse("admin:auth_group_delete", args=[group.pk])
    response = admin_client.post(delete_url, {"post": "yes"})
    assert response.status_code == 302

    # Verify deletion
    assert not Group.objects.filter(pk=group.pk).exists()
