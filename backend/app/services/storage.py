"""Object storage abstraction over S3 (MinIO in dev, AWS S3 in prod)."""

import boto3
from botocore.config import Config

from app.config import get_settings


def _client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(signature_version="s3v4"),
    )


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    settings = get_settings()
    _client().put_object(Bucket=settings.s3_bucket_documents, Key=key, Body=data, ContentType=content_type)


def get_object(key: str) -> bytes:
    settings = get_settings()
    response = _client().get_object(Bucket=settings.s3_bucket_documents, Key=key)
    return response["Body"].read()


def presign_document(key: str, filename: str, expires: int = 900) -> str:
    settings = get_settings()
    params = {"Bucket": settings.s3_bucket_documents, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return _client().generate_presigned_url("get_object", Params=params, ExpiresIn=expires)