from django.conf import settings

import boto3


def client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        endpoint_url=settings.S3_ENDPOINT_URL,
        region_name=settings.S3_REGION_NAME,
    )
