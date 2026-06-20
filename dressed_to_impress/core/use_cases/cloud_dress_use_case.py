"""CloudDressUseCase — orchestrates cloud-based try-on process."""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from urllib.parse import urlparse

from ..commands.cloud_dress_command import CloudDressCommand
from ..commands.dress_command import DressCommand
from ..ports.blob_repository import BlobRepository
from ..ports.errors import InfraError
from ..results.app_result import AppResult
from .dress_use_case import DressUseCase

logger = logging.getLogger(__name__)


class CloudDressUseCase:
    def __init__(
        self,
        blob_repo: BlobRepository,
        dress_use_case: DressUseCase,
        default_input_bucket: str,
        default_output_bucket: str,
        temp_dir_base: str = "/tmp",
    ) -> None:
        self._blob_repo = blob_repo
        self._dress_use_case = dress_use_case
        self._default_input_bucket = default_input_bucket
        self._default_output_bucket = default_output_bucket
        self._temp_dir_base = temp_dir_base

    def execute(self, cmd: CloudDressCommand) -> AppResult[str]:
        logger.info(
            "Starting CloudDressUseCase execution with person_uri=%s, outfit_uri=%s, output_name=%s",
            cmd.person_image_uri,
            cmd.outfit_image_uri,
            cmd.output_image_name,
        )

        # 1. Parse URI and bucket names
        try:
            p_bucket, p_blob = self._parse_uri(
                cmd.person_image_uri, self._default_input_bucket
            )
            o_bucket, o_blob = self._parse_uri(
                cmd.outfit_image_uri, self._default_input_bucket
            )
            out_bucket, out_blob = self._parse_uri(
                cmd.output_image_name, self._default_output_bucket
            )
            logger.debug(
                "Parsed GCS URIs: person=gs://%s/%s, outfit=gs://%s/%s, output=gs://%s/%s",
                p_bucket,
                p_blob,
                o_bucket,
                o_blob,
                out_bucket,
                out_blob,
            )
        except ValueError as err:
            logger.warning("URI parsing failed validation: %s", err)
            return AppResult.invalid([str(err)])

        # 2. Setup isolated temp directory
        run_id = str(uuid.uuid4())
        work_dir = os.path.join(self._temp_dir_base, f"dress_{run_id}")

        local_person = os.path.join(
            work_dir, "person" + os.path.splitext(p_blob)[1]
        )
        local_outfit = os.path.join(
            work_dir, "outfit" + os.path.splitext(o_blob)[1]
        )
        local_output = os.path.join(
            work_dir, "output" + os.path.splitext(out_blob)[1]
        )

        logger.debug("Creating isolated local working directory: %s", work_dir)
        os.makedirs(work_dir, exist_ok=True)

        try:
            # 3. Download files from bucket
            logger.info(
                "Downloading person image from gs://%s/%s -> %s",
                p_bucket,
                p_blob,
                local_person,
            )
            self._blob_repo.download_to_file(p_bucket, p_blob, local_person)

            logger.info(
                "Downloading outfit image from gs://%s/%s -> %s",
                o_bucket,
                o_blob,
                local_outfit,
            )
            self._blob_repo.download_to_file(o_bucket, o_blob, local_outfit)

            # 4. Invoke local DressUseCase
            local_cmd = DressCommand(
                person_image_path=local_person,
                outfit_image_path=local_outfit,
                output_path=local_output,
                prompt_override=cmd.prompt_override,
            )

            logger.info("Executing core DressUseCase locally")
            result = self._dress_use_case.execute(local_cmd)

            if not result.success:
                logger.error(
                    "Core DressUseCase execution failed. Validation: %s, Message: %s",
                    result.validation_errors,
                    result.message,
                )
                return AppResult.failure(
                    f"Core execution failed: {result.message or result.validation_errors}"
                )

            # 5. Upload to destination bucket
            logger.info(
                "Uploading output to gs://%s/%s from local path %s",
                out_bucket,
                out_blob,
                local_output,
            )
            self._blob_repo.upload_from_file(local_output, out_bucket, out_blob)

            destination_uri = f"gs://{out_bucket}/{out_blob}"
            logger.info(
                "Successfully completed CloudDressUseCase. Output uploaded to: %s",
                destination_uri,
            )
            return AppResult.ok(destination_uri, "Process executed successfully.")

        except InfraError as exc:
            logger.exception(
                "Infrastructure failure during cloud dress execution: %s", exc
            )
            return AppResult.failure(f"Infrastructure failure: {exc}")
        except Exception as exc:
            logger.exception(
                "Unhandled exception during cloud dress execution: %s", exc
            )
            return AppResult.failure(f"Unexpected error: {exc}")
        finally:
            # 6. Cleanup local filesystem to prevent memory leaks in Cloud Functions
            logger.debug("Cleaning up local working directory: %s", work_dir)
            try:
                shutil.rmtree(work_dir)
                logger.debug("Cleanup successful.")
            except Exception as cleanup_err:
                logger.warning(
                    "Failed to clean up workspace directory %s: %s",
                    work_dir,
                    cleanup_err,
                )

    def _parse_uri(self, uri: str, default_bucket: str) -> tuple[str, str]:
        if uri.startswith("gs://"):
            parsed = urlparse(uri)
            bucket = parsed.netloc
            blob = parsed.path.lstrip("/")
            if not bucket or not blob:
                raise ValueError(f"Invalid GCS URI: {uri}")
            return bucket, blob
        return default_bucket, uri
