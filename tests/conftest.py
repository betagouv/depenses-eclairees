"""
Global fixtures for all tests
"""

from django.test import Client

import pytest

from tests.factories.users import UserFactory


@pytest.fixture
def admin_client():
    """Create an admin client for testing admin functionality"""
    admin_user = UserFactory(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin_user)
    return client
