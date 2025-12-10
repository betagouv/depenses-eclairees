from django.contrib.auth.models import Permission

import pytest

from docia.permissions import ALLOWED_BATCHES, ALLOWED_EJ_NUMBERS
from docia.tests.factories.data import DataAttachmentFactory, DataBatchFactory, DataEngagementFactory
from docia.tests.factories.users import UserFactory


def create_ej_and_document(**kwargs):
    ej = DataEngagementFactory(**kwargs)
    a = DataAttachmentFactory(ej=ej)
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
    user.user_permissions.add(Permission.objects.get(codename="view_dataattachment"))
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
