import pytest

from docia.tracking.models import TrackingEvent
from tests.docia.views.home.utils import create_ej_and_document, mock_user_perms
from tests.factories.users import UserFactory


@pytest.mark.django_db
def test_home_search_creates_tracking_event(client):
    """Test that a successful search creates a TrackingEvent."""

    # Setup: create test data
    ej, doc = create_ej_and_document()
    user = UserFactory()
    client.force_login(user)

    # Set a realistic user agent for the test
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0"

    # Perform search with valid EJ number and user agent
    with mock_user_perms(authorize=True):
        response = client.get(f"/?num_ej={ej.num_ej}", HTTP_USER_AGENT=user_agent)
        assert response.status_code == 200
        assert doc.filename in response.text

    # Verify tracking event details
    tracking_event = TrackingEvent.objects.latest("created_at")
    assert tracking_event.category == "search"
    assert tracking_event.action == "submit"
    assert tracking_event.name == "ej_search_form"
    assert tracking_event.num_ej == ej.num_ej
    assert tracking_event.user_id == user.id
    assert tracking_event.user_agent == user_agent
    assert tracking_event.page_url.startswith(f"http://testserver/?num_ej={ej.num_ej}")

