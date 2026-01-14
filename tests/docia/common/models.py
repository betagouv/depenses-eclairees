import pytest

from tests.factories.users import UserFactory


@pytest.mark.django_db
def test_model_save_update_fields_will_add_updated_at():
    """
    Test that saving a model with update_fields updates the 'updated_at' field.
    """
    u = UserFactory()
    u.email = "toto@test.local"
    last_updated_at = u.updated_at
    u.save(update_fields=["email"])
    u.refresh_from_db()
    assert u.email == "toto@test.local"
    assert u.updated_at > last_updated_at


@pytest.mark.django_db
def test_model_save_update_fields_can_exclude_updated_at():
    """
    Test that saving a model with update_fields can exclude the 'updated_at' field.
    """
    u = UserFactory()
    u.email = "toto@test.local"
    last_updated_at = u.updated_at
    # Explicitly exclude updated_at from fields
    u.save(update_fields=["email", "-updated_at"])
    u.refresh_from_db()
    assert u.email == "toto@test.local"
    assert u.updated_at == last_updated_at
