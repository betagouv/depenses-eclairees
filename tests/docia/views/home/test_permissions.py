import pytest

from tests.docia.views.home.utils import create_ej_and_document, mock_user_perms
from tests.factories.users import UserFactory


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
    with mock_user_perms(authorize=False) as m:
        response = client.get(f"/?num_ej={ej.num_ej}")
        m.assert_called_once()
    assert "Aucun résultat" in response.text


@pytest.mark.django_db
def test_user_with_perm_and_scope_can_view_ej(client):
    """User has django permission and has the required scope to see the ej."""
    ej, doc = create_ej_and_document()
    user = UserFactory()
    client.force_login(user)
    with mock_user_perms(authorize=True) as m:
        response = client.get(f"/?num_ej={ej.num_ej}")
        m.assert_called_once()
    assert doc.filename in response.text


@pytest.mark.django_db
def test_admin_can_see_anything(client):
    ej, doc = create_ej_and_document()
    user = UserFactory(is_superuser=True)
    client.force_login(user)
    response = client.get(f"/?num_ej={ej.num_ej}")
    assert doc.filename in response.text

