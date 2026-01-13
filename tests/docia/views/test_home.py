from django.contrib.auth.models import Permission

import pytest

from docia.permissions import ALLOWED_BATCHES, ALLOWED_EJ_NUMBERS
from docia.views import compute_ratio_data_extraction, format_ratio_to_percent
from tests.factories.data import DataBatchFactory, DataEngagementFactory, DocumentFactory
from tests.factories.users import UserFactory


def create_ej_and_document(**kwargs):
    ej = DataEngagementFactory(**kwargs)
    a = DocumentFactory(ej=ej)
    return ej, a


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Se connecter" in response.text


@pytest.mark.django_db
def test_home_logged_in(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
    assert user.email in response.text


@pytest.mark.django_db
def test_restrict_unauthenticated(client):
    ej, doc = create_ej_and_document()
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert "Se connecter" in response.text


@pytest.mark.django_db
def test_restrict_no_permission(client):
    ej, doc = create_ej_and_document()
    user = UserFactory()
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert "Aucun résultat" in response.text


@pytest.fixture
def user_with_permission():
    user = UserFactory()
    user.user_permissions.add(Permission.objects.get(codename="view_document"))
    return user


@pytest.fixture
def client_with_permission(client, user_with_permission):
    client.force_login(user_with_permission)
    return client


@pytest.mark.django_db
def test_restrict_ej(client_with_permission):
    ej, doc = create_ej_and_document()
    response = client_with_permission.get(f"/?num_ej={ej.num_ej}")
    assert "Aucun résultat" in response.text


@pytest.mark.django_db
def test_can_access_ej_in_allowed_numbers(client_with_permission):
    num_ej = ALLOWED_EJ_NUMBERS[0]
    ej, doc = create_ej_and_document(num_ej=num_ej)
    response = client_with_permission.get(f"/?num_ej={ej.num_ej}")
    assert doc.filename in response.text


@pytest.mark.django_db
def test_can_access_ej_in_allowed_batches(client_with_permission):
    ej, doc = create_ej_and_document()
    batch_id = ALLOWED_BATCHES[0]
    DataBatchFactory(batch=batch_id, ej=ej)
    response = client_with_permission.get(f"/?num_ej={ej.num_ej}")
    assert doc.filename in response.text


@pytest.mark.django_db
def test_admin_can_see_anything(client):
    ej, doc = create_ej_and_document()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert doc.filename in response.text


def test_compute_ratio_data_extraction():
    """Test compute_ratio_data_extraction function with various inputs."""
    # Empty dictionary should return 0
    assert compute_ratio_data_extraction({}) == 0

    # All values are empty/None/False, should return 0
    assert compute_ratio_data_extraction({"key1": None, "key2": "", "key3": False}) == 0

    # All values are non-empty, should return 1.0
    assert compute_ratio_data_extraction({"key1": "value", "key2": "data", "key3": True}) == 1.0

    # Mix of empty and non-empty values, should return ratio
    response = {"key1": "value", "key2": None, "key3": "data", "key4": ""}
    assert compute_ratio_data_extraction(response) == 0.5

    # More complex example
    complex_response = {
        "field1": "extracted data",
        "field2": None,
        "field3": "",
        "field4": "more data",
        "field5": 123,
        "field6": False,
    }
    # 3 out of 6 have values (field1, field4, field5)
    assert compute_ratio_data_extraction(complex_response) == 0.5


def test_format_ratio_to_percent():
    """Test format_ratio_to_percent function with various inputs."""
    # Zero should return 0%
    assert format_ratio_to_percent(0) == "0%"

    # 0.5 should return 50%
    assert format_ratio_to_percent(0.5) == "50%"

    # 1.0 should return 100%
    assert format_ratio_to_percent(1.0) == "100%"

    # Values are rounded to nearest integer
    assert format_ratio_to_percent(0.333) == "33%"
    assert format_ratio_to_percent(0.667) == "67%"

    # Values greater than 1 are allowed
    assert format_ratio_to_percent(1.5) == "150%"

    # Small values are rounded properly
    assert format_ratio_to_percent(0.01) == "1%"
    assert format_ratio_to_percent(0.001) == "0%"  # Rounds to 0
