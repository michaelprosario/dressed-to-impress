"""Domain value object representing an in-memory image.

The Core reasons about images as raw bytes + a mime type, with no knowledge of
where the bytes came from (disk, network, etc.). This keeps the Core free of any
I/O dependency.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageAsset:
    data: bytes
    mime_type: str
    source_path: str | None = None
