"""Input object for the upload image use case (Command pattern)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadImageCommand:
    filename: str
    data: bytes
    bucket_name: str | None = None
