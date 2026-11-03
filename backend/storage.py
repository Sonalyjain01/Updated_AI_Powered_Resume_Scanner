"""Storage for the original uploaded resumes.

STORAGE_BACKEND:
  local (default)  files under STORAGE_LOCAL_DIR; fine for development
  s3               any S3-compatible store (AWS S3, Cloudflare R2, MinIO) through boto3
  none             do not keep originals

Encrypt the bucket at rest and block public access on it; this module does neither.
"""
import asyncio
import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """A file could not be stored or removed"""


def make_key(scan_id: str, filename: str) -> str:
    """Object key for a scan's original file; the filename is reduced to safe characters"""
    base = os.path.basename((filename or "resume").replace("\\", "/"))
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:100] or "resume"
    return f"resumes/{scan_id}/{safe}"


class FileStorage(ABC):
    name: str = "base"

    async def ensure_ready(self) -> None:
        """Create whatever the backend needs (folder, bucket)"""

    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove an object; removing one that is already gone is not an error"""

    @abstractmethod
    async def exists(self, key: str) -> bool: ...


class LocalFileStorage(FileStorage):
    name = "local"

    def __init__(self, root):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise StorageError("Refusing a key that points outside the storage folder")
        return path

    async def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)

        def write():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        try:
            await asyncio.to_thread(write)
        except OSError as e:
            raise StorageError(f"Could not write {key}: {e}") from e

    async def delete(self, key: str) -> None:
        path = self._path(key)

        def remove():
            path.unlink(missing_ok=True)
            try:
                path.parent.rmdir()  # drop the per-scan folder once empty
            except OSError:
                pass

        try:
            await asyncio.to_thread(remove)
        except OSError as e:
            raise StorageError(f"Could not delete {key}: {e}") from e

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).is_file)


class S3FileStorage(FileStorage):
    name = "s3"

    def __init__(self, bucket: str, endpoint_url: Optional[str] = None, region: Optional[str] = None,
                 access_key_id: Optional[str] = None, secret_access_key: Optional[str] = None):
        import boto3  # imported here so the app runs without boto3 when S3 is not used
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region or None,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
        )

    async def ensure_ready(self) -> None:
        from botocore.exceptions import ClientError

        def check():
            try:
                self._client.head_bucket(Bucket=self.bucket)
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") in ("404", "NoSuchBucket", "NotFound"):
                    self._client.create_bucket(Bucket=self.bucket)
                    logger.info(f"Created storage bucket {self.bucket}")
                else:
                    raise

        try:
            await asyncio.to_thread(check)
        except Exception as e:
            raise StorageError(f"Storage bucket '{self.bucket}' is not usable: {e}") from e

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self._client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
            )
        except Exception as e:
            raise StorageError(f"Could not upload {key}: {e}") from e

    async def delete(self, key: str) -> None:
        try:  # S3 reports success when the key is already gone
            await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=key)
        except Exception as e:
            raise StorageError(f"Could not delete {key}: {e}") from e

    async def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError
        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise StorageError(f"Could not check {key}: {e}") from e


def get_storage() -> Optional[FileStorage]:
    """The configured storage, or None when originals are not kept"""
    backend = os.getenv("STORAGE_BACKEND", "local").lower()
    if backend == "none":
        return None
    if backend == "local":
        root = os.getenv("STORAGE_LOCAL_DIR") or str(Path(__file__).parent / "storage")
        return LocalFileStorage(root)
    if backend == "s3":
        return S3FileStorage(
            bucket=os.getenv("S3_BUCKET", ""),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            region=os.getenv("S3_REGION"),
            access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        )
    raise ValueError(f"Unknown STORAGE_BACKEND '{backend}'. Use 'local', 's3' or 'none'.")
