from django.contrib.auth import get_user_model
from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from docia.tracking.models import TrackingEvent
from tests.factories.users import UserFactory

User = get_user_model()
now = "2025-10-08T10:00:00+00:00"


@pytest.fixture
def api_client():
    """Return an authenticated API client."""
    return APIClient()


@pytest.fixture
def authenticated_api_client():
    """Return an authenticated API client with a logged-in user."""
    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
def test_authentication_required(api_client):
    """Test that authentication is required for the endpoint."""
    url = reverse("tracking-event-create")  # Make sure you've named your URL pattern

    data = {"category": "test", "action": "click", "name": "button"}

    response = api_client.post(url, data)
    assert response.status_code == 403  # Unauthorized


@pytest.mark.django_db
def test_create_tracking_event(authenticated_api_client):
    """Test creating a tracking event with basic data."""
    client, user = authenticated_api_client
    url = reverse("tracking-event-create")

    data = {"category": "test", "action": "click", "name": "button"}

    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    referer = "https://example.com/documents"

    with freeze_time(now):
        response = client.post(
            url,
            data,
            format="json",
            HTTP_REFERER=referer,
            HTTP_USER_AGENT=user_agent,
        )

    assert response.status_code == 204
    assert response.content == b""

    # Verify the event was created in the database
    event = TrackingEvent.objects.last()
    assert event.category == "test"
    assert event.action == "click"
    assert event.name == "button"
    assert event.user == user
    assert event.page_url == referer
    assert event.user_agent == user_agent
    assert event.created_at.isoformat() == now


@pytest.mark.django_db
def test_missing_required_fields(authenticated_api_client):
    """Test that required fields validation works."""
    client, _ = authenticated_api_client
    url = reverse("tracking-event-create")

    # Missing required fields
    data = {}

    response = client.post(url, data, format="json")
    assert response.status_code == 400
    assert "category" in response.data
    assert "action" in response.data
    assert "name" in response.data
