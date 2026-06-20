"""Unit tests for CloudDressUseCase — no disk, no GCS network."""

from __future__ import annotations

import os
import pytest

from dressed_to_impress.core.commands.cloud_dress_command import CloudDressCommand
from dressed_to_impress.core.ports.errors import InfraError
from dressed_to_impress.core.use_cases.cloud_dress_use_case import CloudDressUseCase
from dressed_to_impress.core.use_cases.dress_use_case import DressUseCase
from tests.fakes import FakeImageGenerationProvider, FakeImageRepository


class FakeBlobRepository:
    def __init__(
        self,
        existing_blobs: dict[str, bytes] | None = None,
        image_repo: FakeImageRepository | None = None,
    ) -> None:
        self.blobs = dict(existing_blobs or {})
        self._image_repo = image_repo
        self.downloads: list[tuple[str, str, str]] = []
        self.uploads: list[tuple[str, str, str]] = []

    def download_to_file(
        self, bucket_name: str, blob_name: str, local_path: str
    ) -> None:
        key = f"gs://{bucket_name}/{blob_name}"
        if key not in self.blobs:
            raise InfraError(f"Blob not found: {key}")
        self.downloads.append((bucket_name, blob_name, local_path))
        
        # Write to fake local image repository so it knows the file exists in-memory
        if self._image_repo is not None:
            self._image_repo.files[local_path] = self.blobs[key]

        # Also write to actual disk in case the directory/file structure is checked by OS
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(self.blobs[key])

    def upload_from_file(
        self, local_path: str, bucket_name: str, blob_name: str
    ) -> None:
        self.uploads.append((local_path, bucket_name, blob_name))
        
        # Check in the fake local repository's written files first
        if self._image_repo is not None and local_path in self._image_repo.written:
            self.blobs[f"gs://{bucket_name}/{blob_name}"] = self._image_repo.written[local_path]
        else:
            with open(local_path, "rb") as f:
                self.blobs[f"gs://{bucket_name}/{blob_name}"] = f.read()


def test_cloud_use_case_happy_path(tmp_path):
    # Setup fakes
    blobs = {
        "gs://in-bucket/person.png": b"person-bytes",
        "gs://in-bucket/outfit.png": b"outfit-bytes",
    }
    
    # Instantiate repositories
    local_repo = FakeImageRepository()
    blob_repo = FakeBlobRepository(blobs, image_repo=local_repo)
    provider = FakeImageGenerationProvider(result=b"output-image-bytes")
    dress_use_case = DressUseCase(repo=local_repo, provider=provider)

    cloud_use_case = CloudDressUseCase(
        blob_repo=blob_repo,
        dress_use_case=dress_use_case,
        default_input_bucket="in-bucket",
        default_output_bucket="out-bucket",
        temp_dir_base=str(tmp_path),
    )

    cmd = CloudDressCommand(
        person_image_uri="gs://in-bucket/person.png",
        outfit_image_uri="gs://in-bucket/outfit.png",
        output_image_name="dressed_output.png",
    )

    result = cloud_use_case.execute(cmd)

    assert result.success
    assert result.value == "gs://out-bucket/dressed_output.png"
    assert "gs://out-bucket/dressed_output.png" in blob_repo.blobs
    assert (
        blob_repo.blobs["gs://out-bucket/dressed_output.png"]
        == b"output-image-bytes"
    )
    assert not os.path.exists(
        os.path.join(tmp_path, f"dress_{os.path.basename(result.value)}")
    )  # workspace cleaned up


def test_cloud_use_case_uri_validation_error(tmp_path):
    local_repo = FakeImageRepository()
    blob_repo = FakeBlobRepository(image_repo=local_repo)
    provider = FakeImageGenerationProvider()
    dress_use_case = DressUseCase(repo=local_repo, provider=provider)

    cloud_use_case = CloudDressUseCase(
        blob_repo=blob_repo,
        dress_use_case=dress_use_case,
        default_input_bucket="in-bucket",
        default_output_bucket="out-bucket",
        temp_dir_base=str(tmp_path),
    )

    # Invalid URI (empty gs:// URI path)
    cmd = CloudDressCommand(
        person_image_uri="gs://",
        outfit_image_uri="gs://in-bucket/outfit.png",
        output_image_name="dressed_output.png",
    )

    result = cloud_use_case.execute(cmd)

    assert not result.success
    assert any("Invalid GCS URI" in err for err in result.validation_errors)


def test_cloud_use_case_blob_not_found(tmp_path):
    blobs = {
        "gs://in-bucket/person.png": b"person-bytes",
        # outfit missing
    }
    local_repo = FakeImageRepository()
    blob_repo = FakeBlobRepository(blobs, image_repo=local_repo)
    provider = FakeImageGenerationProvider()
    dress_use_case = DressUseCase(repo=local_repo, provider=provider)

    cloud_use_case = CloudDressUseCase(
        blob_repo=blob_repo,
        dress_use_case=dress_use_case,
        default_input_bucket="in-bucket",
        default_output_bucket="out-bucket",
        temp_dir_base=str(tmp_path),
    )

    cmd = CloudDressCommand(
        person_image_uri="gs://in-bucket/person.png",
        outfit_image_uri="gs://in-bucket/outfit.png",
        output_image_name="dressed_output.png",
    )

    result = cloud_use_case.execute(cmd)

    assert not result.success
    assert "Infrastructure failure" in result.message
    assert "Blob not found" in result.message


def test_cloud_use_case_inner_validation_error(tmp_path):
    # Setup fakes but with unsupported file extensions
    blobs = {
        "gs://in-bucket/person.gif": b"person-bytes",  # gif unsupported
        "gs://in-bucket/outfit.png": b"outfit-bytes",
    }
    local_repo = FakeImageRepository()
    blob_repo = FakeBlobRepository(blobs, image_repo=local_repo)
    provider = FakeImageGenerationProvider()
    dress_use_case = DressUseCase(repo=local_repo, provider=provider)

    cloud_use_case = CloudDressUseCase(
        blob_repo=blob_repo,
        dress_use_case=dress_use_case,
        default_input_bucket="in-bucket",
        default_output_bucket="out-bucket",
        temp_dir_base=str(tmp_path),
    )

    cmd = CloudDressCommand(
        person_image_uri="gs://in-bucket/person.gif",
        outfit_image_uri="gs://in-bucket/outfit.png",
        output_image_name="dressed_output.png",
    )

    result = cloud_use_case.execute(cmd)

    assert not result.success
    assert "Core execution failed" in result.message
    assert "person image must be one of" in result.message
