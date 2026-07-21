"""S3 / MinIO compatible object storage client."""
from __future__ import annotations

import json
import uuid
from typing import Optional

import aioboto3
from botocore.config import Config

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Public-read policy so direct MinIO URLs also work (WordPress, external tools).
_PUBLIC_READ_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{settings.S3_BUCKET}/*"],
        }
    ],
}


class ObjectStorage:
    """Thin async wrapper around aioboto3 for the media bucket."""

    def __init__(self) -> None:
        self._session = aioboto3.Session()
        self._bucket = settings.S3_BUCKET
        self._config = Config(signature_version="s3v4")

    def _client(self):
        return self._session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            use_ssl=settings.S3_USE_SSL,
            config=self._config,
        )

    async def ensure_bucket(self) -> None:
        async with self._client() as client:
            try:
                await client.head_bucket(Bucket=self._bucket)
            except Exception:
                logger.info("Creating bucket %s", self._bucket)
                await client.create_bucket(Bucket=self._bucket)
            try:
                await client.put_bucket_policy(
                    Bucket=self._bucket, Policy=json.dumps(_PUBLIC_READ_POLICY)
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Could not set public-read policy: %s", exc)

    @staticmethod
    def build_key(prefix: str, filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        return f"{prefix}/{uuid.uuid4().hex}.{ext}"

    async def upload_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        async with self._client() as client:
            await client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        return self.public_url(key)

    async def download_bytes(self, key: str) -> bytes:
        async with self._client() as client:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()

    async def delete(self, key: str) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=self._bucket, Key=key)

    async def presigned_url(self, key: str, expires_in: int = 3600) -> str:
        async with self._client() as client:
            return await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )

    def public_url(self, key: str) -> str:
        """Return a same-origin API proxy URL so the Vite UI can load images.

        Direct MinIO URLs also work after ensure_bucket applies public-read.
        """
        return f"{settings.API_V1_PREFIX}/media/{key}"

    def direct_url(self, key: str) -> str:
        base = settings.S3_PUBLIC_URL.rstrip("/")
        return f"{base}/{key}"


storage = ObjectStorage()
