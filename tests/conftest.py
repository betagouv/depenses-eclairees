import os

from django.test import Client

import boto3
import pytest
from moto import mock_aws

from tests.factories.users import UserFactory


@pytest.fixture(scope="session", autouse=True)
def s3_client():
    # Set the MOTO_S3_CUSTOM_ENDPOINTS from Django settings S3_ENDPOINT_URL
    endpoint = "https://s3.testing.beta.gouv.fr"
    os.environ["MOTO_S3_CUSTOM_ENDPOINTS"] = endpoint

    with mock_aws():
        s3 = boto3.resource(
            "s3", region_name="eu", endpoint_url=endpoint, aws_access_key_id="", aws_secret_access_key=""
        )
        s3.create_bucket(Bucket="test-depec")
        yield s3


@pytest.fixture
def admin_client():
    """Create an admin client for testing admin functionality"""
    admin_user = UserFactory(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin_user)
    return client
