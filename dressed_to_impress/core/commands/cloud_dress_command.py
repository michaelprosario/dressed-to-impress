"""Input object for the cloud dress use case (Command pattern)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudDressCommand:
    person_image_uri: str  # gs://bucket/path/person.png or path/person.png
    outfit_image_uri: str  # gs://bucket/path/outfit.jpg or path/outfit.jpg
    output_image_name: str  # path/dressed.png
    prompt_override: str | None = None
