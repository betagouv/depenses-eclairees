"""
Test cases for the Django admin interface, specifically for TrackingEvent administration.
Tests the search and filter functionality on the TrackingEvent model.
"""

from django.urls import reverse

import pytest

from tests.factories.tracking import TrackingEventFactory


@pytest.mark.django_db
def test_tracking_event_admin_list_view(admin_client):
    """Test that the TrackingEvent list view in admin shows events"""
    # Create test tracking events using factory (user is created automatically)
    event_list_1 = TrackingEventFactory()
    event_list_2 = TrackingEventFactory()

    # Get the TrackingEvent list URL
    list_url = reverse("admin:docia_trackingevent_changelist")

    # Test GET request
    response = admin_client.get(list_url)
    assert response.status_code == 200

    # Check that events appear in the list
    assert str(event_list_1.id) in response.text
    assert str(event_list_2.id) in response.text
    assert event_list_1.category in response.text
    assert event_list_2.category in response.text
    assert event_list_1.action in response.text
    assert event_list_2.action in response.text
    assert event_list_1.name in response.text
    assert event_list_2.name in response.text
    assert event_list_1.user.email in response.text
    assert event_list_2.user.email in response.text
    assert event_list_1.num_ej in response.text
    assert event_list_2.num_ej in response.text
    assert event_list_1.page_url in response.text
    assert event_list_2.page_url in response.text


@pytest.mark.django_db
def test_tracking_event_admin_search_by_action(admin_client):
    """Test that TrackingEventAdmin search works correctly on action field"""
    # Create 2 positive events with same action and 2 negative events with different actions
    event_action_search_1 = TrackingEventFactory(
        action="test_action_search",
    )
    event_action_search_2 = TrackingEventFactory(
        action="test_action_search",
    )
    event_action_other_1 = TrackingEventFactory(
        action="test_action_other",
    )
    event_action_other_2 = TrackingEventFactory(
        action="test_action_other",
    )

    # Get the TrackingEvent list URL
    list_url = reverse("admin:docia_trackingevent_changelist")

    # Search for the test action
    search_url = f"{list_url}?q={event_action_search_1.action}"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that search events appear and other events don't
    assert str(event_action_search_1.id) in response.text
    assert str(event_action_search_2.id) in response.text
    assert str(event_action_other_1.id) not in response.text
    assert str(event_action_other_2.id) not in response.text


@pytest.mark.django_db
def test_tracking_event_admin_search_by_category(admin_client):
    """Test that TrackingEventAdmin search works correctly on category field"""
    # Create 2 positive events with same category and 2 negative events with different categories
    event_category_search_1 = TrackingEventFactory(
        category="test_category_search",
    )
    event_category_search_2 = TrackingEventFactory(
        category="test_category_search",
    )
    event_category_other_1 = TrackingEventFactory(
        category="test_category_other",
    )
    event_category_other_2 = TrackingEventFactory(
        category="test_category_other",
    )

    # Get the TrackingEvent list URL
    list_url = reverse("admin:docia_trackingevent_changelist")

    # Search for the test category
    search_url = f"{list_url}?q={event_category_search_1.category}"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that search events appear and other events don't
    assert str(event_category_search_1.id) in response.text
    assert str(event_category_search_2.id) in response.text
    assert str(event_category_other_1.id) not in response.text
    assert str(event_category_other_2.id) not in response.text


@pytest.mark.django_db
def test_tracking_event_admin_search_by_num_ej(admin_client):
    """Test that TrackingEventAdmin search works correctly on num_ej field"""
    # Create 2 positive events with same num_ej and 2 negative events with different num_ej
    event_num_ej_search_1 = TrackingEventFactory(num_ej="EJ1234567890")
    event_num_ej_search_2 = TrackingEventFactory(num_ej="EJ1234567890")
    event_num_ej_other_1 = TrackingEventFactory(num_ej="EJ0987654321")
    event_num_ej_other_2 = TrackingEventFactory(num_ej="EJ0987654321")

    # Get the TrackingEvent list URL
    list_url = reverse("admin:docia_trackingevent_changelist")

    # Test search for the test num_ej
    search_url = f"{list_url}?q={event_num_ej_search_1.num_ej}"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that search events appear and other events don't
    assert str(event_num_ej_search_1.id) in response.text
    assert str(event_num_ej_search_2.id) in response.text
    assert str(event_num_ej_other_1.id) not in response.text
    assert str(event_num_ej_other_2.id) not in response.text


@pytest.mark.django_db
def test_tracking_event_admin_filter_by_action(admin_client):
    """Test that TrackingEventAdmin filter works correctly on action field"""
    # Create 2 positive events with same action and 2 negative events with different actions
    event_filter_action_1 = TrackingEventFactory(
        action="test_action_filter",
    )
    event_filter_action_2 = TrackingEventFactory(
        action="test_action_filter",
    )
    event_filter_other_1 = TrackingEventFactory(
        action="test_action_other",
    )
    event_filter_other_2 = TrackingEventFactory(
        action="test_action_other",
    )

    # Get the TrackingEvent list URL
    list_url = reverse("admin:docia_trackingevent_changelist")

    # Test filter for the test action
    filter_url = f"{list_url}?action={event_filter_action_1.action}"
    response = admin_client.get(filter_url)
    assert response.status_code == 200

    # Check that filter events appear and other events don't
    assert str(event_filter_action_1.id) in response.text
    assert str(event_filter_action_2.id) in response.text
    assert str(event_filter_other_1.id) not in response.text
    assert str(event_filter_other_2.id) not in response.text


@pytest.mark.django_db
def test_tracking_event_admin_filter_by_category(admin_client):
    """Test that TrackingEventAdmin filter works correctly on category field"""
    # Create 2 positive events with same category and 2 negative events with different categories
    event_filter_category_1 = TrackingEventFactory(
        category="test_category_filter",
    )
    event_filter_category_2 = TrackingEventFactory(
        category="test_category_filter",
    )
    event_filter_other_1 = TrackingEventFactory(
        category="test_category_other",
    )
    event_filter_other_2 = TrackingEventFactory(
        category="test_category_other",
    )

    # Get the TrackingEvent list URL
    list_url = reverse("admin:docia_trackingevent_changelist")

    # Test filter for the test category
    filter_url = f"{list_url}?category={event_filter_category_1.category}"
    response = admin_client.get(filter_url)
    assert response.status_code == 200

    # Check that filter events appear and other events don't
    assert str(event_filter_category_1.id) in response.text
    assert str(event_filter_category_2.id) in response.text
    assert str(event_filter_other_1.id) not in response.text
    assert str(event_filter_other_2.id) not in response.text


@pytest.mark.django_db
def test_tracking_event_admin_combined_search_and_filter(admin_client):
    """Test that TrackingEventAdmin works with combined search and filter"""
    # Create 2 positive events matching both criteria and 2 negative events
    event_combined_positive_1 = TrackingEventFactory(action="test_action_combined", num_ej="EJ1234567890")
    event_combined_positive_2 = TrackingEventFactory(action="test_action_combined", num_ej="EJ1234567890")
    event_combined_negative_1 = TrackingEventFactory(action="test_action_other", num_ej="EJ1234567890")
    event_combined_negative_2 = TrackingEventFactory(action="test_action_combined", num_ej="EJ0987654321")

    # Get the TrackingEvent list URL
    list_url = reverse("admin:docia_trackingevent_changelist")

    # Test combined search and filter
    combined_url = f"{list_url}?q={event_combined_positive_1.num_ej}&action={event_combined_positive_1.action}"
    response = admin_client.get(combined_url)
    assert response.status_code == 200

    # Check that positive events appear and negative events don't
    assert str(event_combined_positive_1.id) in response.text
    assert str(event_combined_positive_2.id) in response.text
    assert str(event_combined_negative_1.id) not in response.text
    assert str(event_combined_negative_2.id) not in response.text


@pytest.mark.django_db
def test_tracking_event_admin_search_by_user_email(admin_client):
    """Test that TrackingEventAdmin search works correctly on user email field"""
    # Create 2 positive events with same user and 2 negative events with different users
    event_user_search_1 = TrackingEventFactory()
    event_user_search_2 = TrackingEventFactory(user=event_user_search_1.user)
    event_user_other_1 = TrackingEventFactory()
    event_user_other_2 = TrackingEventFactory()

    # Get the TrackingEvent list URL
    list_url = reverse("admin:docia_trackingevent_changelist")

    # Search for the test user email
    search_url = f"{list_url}?q={event_user_search_1.user.email}"
    response = admin_client.get(search_url)
    assert response.status_code == 200

    # Check that search events appear and other events don't
    assert str(event_user_search_1.id) in response.text
    assert str(event_user_search_2.id) in response.text
    assert str(event_user_other_1.id) not in response.text
    assert str(event_user_other_2.id) not in response.text
