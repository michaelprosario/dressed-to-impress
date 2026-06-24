"""Port for a cloud blob storage repository. Implemented by Infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BlobRepository(ABC):
    @abstractmethod
    def download_to_file(
        self, bucket_name: str, blob_name: str, local_path: str
    ) -> None:
        """Download an object from the specified bucket to a local path.

        Raises InfraError on failure.
        """

    @abstractmethod
    def upload_from_file(
        self, local_path: str, bucket_name: str, blob_name: str
    ) -> None:
        """Upload a local file to the specified storage bucket.

        Raises InfraError on failure.
        """
