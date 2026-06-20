"""UploadImageUseCase — validates and uploads a file to GCS."""

from __future__ import annotations

import logging
import os
import tempfile

from ..commands.upload_image_command import UploadImageCommand
from ..ports.blob_repository import BlobRepository
from ..ports.errors import InfraError
from ..results.app_result import AppResult

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


class UploadImageUseCase:
    def __init__(self, blob_repo: BlobRepository, default_bucket: str) -> None:
        self._blob_repo = blob_repo
        self._default_bucket = default_bucket

    def execute(self, cmd: UploadImageCommand) -> AppResult[str]:
        logger.info(
            "Executing UploadImageUseCase for filename=%s to bucket=%s",
            cmd.filename,
            cmd.bucket_name,
        )

        # 1. Validation
        errors = []
        if not cmd.filename or not cmd.filename.strip():
            errors.append("Filename is required")
            ext = ""
        else:
            _, ext = os.path.splitext(cmd.filename.lower())
            if ext not in SUPPORTED_EXTENSIONS:
                errors.append(
                    f"Unsupported file type. Must be one of {', '.join(SUPPORTED_EXTENSIONS)}"
                )

        if not cmd.data:
            errors.append("File content data is empty or missing")

        if errors:
            logger.warning("Upload validation failed: %s", errors)
            return AppResult.invalid(errors)

        # 2. Upload
        target_bucket = cmd.bucket_name or self._default_bucket
        safe_name = os.path.basename(cmd.filename)

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                temp_file.write(cmd.data)
                temp_path = temp_file.name

            logger.info(
                "Uploading local temp file %s to bucket %s as %s",
                temp_path,
                target_bucket,
                safe_name,
            )
            self._blob_repo.upload_from_file(temp_path, target_bucket, safe_name)

            # Cleanup temp file
            try:
                os.remove(temp_path)
            except Exception as cleanup_err:
                logger.warning(
                    "Failed to clean up temp file %s: %s",
                    temp_path,
                    cleanup_err,
                )

            gcs_uri = f"gs://{target_bucket}/{safe_name}"
            logger.info("Successfully uploaded file. GCS URI: %s", gcs_uri)
            return AppResult.ok(gcs_uri, "File uploaded successfully.")

        except InfraError as exc:
            logger.exception("Infrastructure failure during upload: %s", exc)
            return AppResult.failure(f"Infrastructure failure: {exc}")
        except Exception as exc:
            logger.exception("Unexpected error during upload: %s", exc)
            return AppResult.failure(f"Unexpected error: {exc}")
