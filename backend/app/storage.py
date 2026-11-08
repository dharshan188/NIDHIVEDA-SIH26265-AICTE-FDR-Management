"""Object storage for documents. Only ciphertext is ever written here (see crypto.seal_document).

- `S3Store`: any S3-compatible service (MinIO, AWS S3, SeaweedFS). Configured with TL_S3_* variables.
- `FilesystemStore`: a directory, for tests and for a laptop demo without the object-store container.
"""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from .config import BACKEND_DIR, get_settings


class ObjectStore(Protocol):
    name: str

    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class FilesystemStore:
    name = "filesystem"

    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        if ".." in key or key.startswith("/"):
            raise ValueError("invalid object key")
        return self.root / key

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3Store:
    name = "s3"

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool, region: str = "us-east-1"):
        from minio import Minio  # S3 client; speaks plain S3, not only MinIO
        self.c = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure, region=region)
        self.bucket = bucket
        if not self.c.bucket_exists(bucket):
            self.c.make_bucket(bucket)

    def put(self, key: str, data: bytes) -> None:
        self.c.put_object(self.bucket, key, io.BytesIO(data), len(data), content_type="application/octet-stream")

    def get(self, key: str) -> bytes:
        r = self.c.get_object(self.bucket, key)
        try:
            return r.read()
        finally:
            r.close()
            r.release_conn()

    def exists(self, key: str) -> bool:
        from minio.error import S3Error
        try:
            self.c.stat_object(self.bucket, key)
            return True
        except S3Error:
            return False


@lru_cache
def store() -> ObjectStore:
    s = get_settings()
    if s.object_store == "s3":
        return S3Store(s.s3_endpoint, s.s3_access_key, s.s3_secret_key, s.s3_bucket, s.s3_secure)
    root = Path(s.object_dir) if s.object_dir else BACKEND_DIR / "objects"
    return FilesystemStore(root)
