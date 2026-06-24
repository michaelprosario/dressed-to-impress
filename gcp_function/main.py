"""Google Cloud Function trigger/handler for virtual try-on and upload requests."""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import functions_framework

from dressed_to_impress.core.commands.cloud_dress_command import CloudDressCommand
from dressed_to_impress.core.commands.upload_image_command import UploadImageCommand
from dressed_to_impress.core.use_cases.cloud_dress_use_case import CloudDressUseCase
from dressed_to_impress.core.use_cases.dress_use_case import DressUseCase
from dressed_to_impress.core.use_cases.upload_image_use_case import UploadImageUseCase
from dressed_to_impress.infra.filesystem_image_repository import (
    FilesystemImageRepository,
)
from dressed_to_impress.infra.gemini_image_provider import GeminiImageProvider
from dressed_to_impress.infra.gcs_blob_repository import GcsBlobRepository

# Configure logging to write structured output to stdout (which Google Cloud Logging captures)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("dressCloudFunction")

# Global configuration from Env Vars
INPUT_BUCKET = os.environ.get("INPUT_BUCKET", "dressed-to-impress-inputs")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "dressed-to-impress-outputs")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Composition Roots for the Cloud Function (Lazy initialization for performance)
_cloud_use_case = None
_upload_use_case = None


def get_cloud_use_case() -> CloudDressUseCase:
    global _cloud_use_case
    if _cloud_use_case is None:
        logger.info("Initializing composition root for cloud function...")
        if not GEMINI_API_KEY:
            logger.critical(
                "GEMINI_API_KEY environment variable is not configured. Execution cannot proceed."
            )
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not configured."
            )

        # Core & Infra wiring
        logger.info(
            "Instantiating GcsBlobRepository, FilesystemImageRepository, and GeminiImageProvider"
        )
        blob_repo = GcsBlobRepository()
        local_repo = FilesystemImageRepository()
        gemini_provider = GeminiImageProvider(api_key=GEMINI_API_KEY)

        dress_use_case = DressUseCase(repo=local_repo, provider=gemini_provider)
        _cloud_use_case = CloudDressUseCase(
            blob_repo=blob_repo,
            dress_use_case=dress_use_case,
            default_input_bucket=INPUT_BUCKET,
            default_output_bucket=OUTPUT_BUCKET,
        )
        logger.info("CloudDressUseCase successfully initialized.")
    return _cloud_use_case


def get_upload_use_case() -> UploadImageUseCase:
    global _upload_use_case
    if _upload_use_case is None:
        logger.info("Initializing upload composition root for cloud function...")
        blob_repo = GcsBlobRepository()
        _upload_use_case = UploadImageUseCase(
            blob_repo=blob_repo,
            default_bucket=INPUT_BUCKET,
        )
        logger.info("UploadImageUseCase successfully initialized.")
    return _upload_use_case


# Entry point for Pub/Sub triggers
@functions_framework.cloud_event
def dress_pubsub_handler(cloud_event) -> None:
    """Triggered from a message on a Cloud Pub/Sub topic."""
    event_id = cloud_event.data.get("message", {}).get("messageId", "unknown")
    logger.info("Received Pub/Sub cloud event with messageId: %s", event_id)
    try:
        # Pub/Sub payload is base64 encoded in cloud_event.data["message"]["data"]
        pubsub_data = cloud_event.data["message"]["data"]
        message_str = base64.b64decode(pubsub_data).decode("utf-8")
        payload = json.loads(message_str)
        logger.debug(
            "Decoded Pub/Sub payload for messageId %s: %s", event_id, payload
        )
    except Exception as exc:
        logger.exception(
            "Failed to parse Pub/Sub message payload for event %s: %s",
            event_id,
            exc,
        )
        return

    _execute_payload(payload)


# Entry point for HTTP triggers (e.g. Cloud Tasks)
@functions_framework.http
def dress_http_handler(request):
    """Triggered from an HTTP POST request (e.g., from Cloud Tasks)."""
    logger.info(
        "Received HTTP request to dress_http_handler. Method: %s",
        request.method,
    )
    if request.method != "POST":
        logger.warning(
            "Method %s rejected. Only POST method is accepted.", request.method
        )
        return "Only POST method is accepted", 405

    try:
        payload = request.get_json(silent=True)
        if not payload:
            logger.warning("Empty or invalid JSON body received in HTTP request.")
            return "Invalid JSON body", 400
    except Exception as exc:
        logger.exception("Error parsing HTTP request JSON payload: %s", exc)
        return f"Error parsing JSON payload: {exc}", 400

    result = _execute_payload(payload)
    if result.success:
        return {"status": "success", "output_uri": result.value}, 200

    if result.validation_errors:
        return {
            "status": "validation_error",
            "errors": result.validation_errors,
        }, 400
    return {"status": "failure", "message": result.message}, 500


# Entry point for uploading files
@functions_framework.http
def upload_handler(request):
    """HTTP trigger to upload a file to the storage bucket."""
    logger.info(
        "Received HTTP request to upload_handler. Method: %s", request.method
    )
    if request.method != "POST":
        logger.warning(
            "Method %s rejected. Only POST method is accepted.", request.method
        )
        return "Only POST method is accepted", 405

    # Check if file is in multipart form-data
    if "file" not in request.files:
        logger.warning("No file part in the multipart form-data request.")
        return "Missing 'file' parameter in multipart form data", 400

    file = request.files["file"]
    filename = file.filename
    if not filename:
        logger.warning("Empty filename received in upload request.")
        return "Empty filename", 400

    file_bytes = file.read()
    bucket_override = request.form.get("bucket")

    cmd = UploadImageCommand(
        filename=filename,
        data=file_bytes,
        bucket_name=bucket_override,
    )

    try:
        use_case = get_upload_use_case()
        result = use_case.execute(cmd)

        if result.success:
            return {"status": "success", "gcs_uri": result.value}, 200

        if result.validation_errors:
            return {
                "status": "validation_error",
                "errors": result.validation_errors,
            }, 400
        return {"status": "failure", "message": result.message}, 500
    except Exception as exc:
        logger.exception("Unexpected exception inside upload_handler: %s", exc)
        return {
            "status": "failure",
            "message": f"Unexpected internal failure: {exc}",
        }, 500


def _execute_payload(payload: dict):
    # Parse payload fields
    person_image = payload.get("person_image")
    outfit_image = payload.get("outfit_image")
    output_image_name = payload.get("output_image_name")
    prompt_override = payload.get("prompt_override")

    logger.info(
        "Processing execution payload: person_image=%s, outfit_image=%s, output_image_name=%s",
        person_image,
        outfit_image,
        output_image_name,
    )

    cmd = CloudDressCommand(
        person_image_uri=person_image,
        outfit_image_uri=outfit_image,
        output_image_name=output_image_name,
        prompt_override=prompt_override,
    )

    try:
        use_case = get_cloud_use_case()
        result = use_case.execute(cmd)

        if result.success:
            logger.info(
                "✓ Successfully processed dress execution. Output uploaded to: %s",
                result.value,
            )
        else:
            logger.error(
                "✗ Failed to process dress execution. Validation: %s, Error: %s",
                result.validation_errors,
                result.message,
            )
        return result
    except Exception as exc:
        logger.exception("Unexpected exception inside _execute_payload: %s", exc)
        return AppResult.failure(f"Unexpected internal failure: {exc}")
