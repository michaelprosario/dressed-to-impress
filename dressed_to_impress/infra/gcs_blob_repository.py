"""Google Cloud Storage (GCS) implementation of the BlobRepository port."""

from __future__ import annotations

from google.cloud import storage

from ..core.ports.blob_repository import BlobRepository
from ..core.ports.errors import InfraError


class GcsBlobRepository(BlobRepository):
    def __init__(self, client: storage.Client | None = None) -> None:
        self._client = client or storage.Client()

    def download_to_file(
        self, bucket_name: str, blob_name: str, local_path: str
    ) -> None:
        try:
            bucket = self._client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.download_to_filename(local_path)
        except Exception as exc:
            raise InfraError(
                f"Failed to download blob gs://{bucket_name}/{blob_name}: {exc}"
            ) from exc

    def upload_from_file(
        self, local_path: str, bucket_name: str, blob_name: str
    ) -> None:
        try:
            bucket = self._client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(local_path)
        except Exception as exc:
            raise InfraError(
                f"Failed to upload {local_path} to gs://{bucket_name}/{blob_name}: {exc}"
            ) from exc
