"""S3 / S3-compatible object storage with presigned URLs.

When ``S3_BUCKET_NAME`` is set the app uploads/downloads files
straight from S3 and the API only brokers signed URLs — no bytes
flow through the backend.  When it's empty we fall back to the
local-FS implementation in ``file_service`` and this module
exposes ``is_enabled() == False`` so callers can degrade.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from app.config import settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client():
    import boto3

    kwargs = {
        "region_name": settings.S3_REGION,
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID or None,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY or None,
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


def is_enabled() -> bool:
    return bool(settings.S3_BUCKET_NAME)


def generate_upload_url(
    key: str,
    content_type: str = "application/octet-stream",
    expires_in: Optional[int] = None,
) -> str:
    """Return a presigned PUT URL the browser can upload to directly."""
    if not is_enabled():
        raise RuntimeError("S3 is not configured")
    return _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in or settings.S3_PRESIGN_EXPIRES_SECONDS,
    )


def generate_download_url(
    key: str,
    expires_in: Optional[int] = None,
    response_content_type: Optional[str] = None,
) -> str:
    """Return a presigned GET URL the browser can fetch from directly."""
    if not is_enabled():
        raise RuntimeError("S3 is not configured")
    params = {
        "Bucket": settings.S3_BUCKET_NAME,
        "Key": key,
    }
    if response_content_type:
        params["ResponseContentType"] = response_content_type
    return _client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in or settings.S3_PRESIGN_EXPIRES_SECONDS,
    )


def delete_object(key: str) -> None:
    """Remove an object.  Used by the GDPR purge job."""
    if not is_enabled():
        return
    _client().delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
