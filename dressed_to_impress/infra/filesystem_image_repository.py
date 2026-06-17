"""Filesystem-backed implementation of the ImageRepository port."""

from __future__ import annotations

import os

from ..core.domain.image_asset import ImageAsset
from ..core.ports.errors import InfraError
from ..core.ports.image_repository import ImageRepository

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class FilesystemImageRepository(ImageRepository):
    def read(self, path: str) -> ImageAsset:
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            raise InfraError(f"could not read image '{path}': {exc}") from exc

        return ImageAsset(
            data=data, mime_type=self._mime_for(path), source_path=path
        )

    def write(self, path: str, data: bytes) -> str:
        abs_path = os.path.abspath(path)
        parent = os.path.dirname(abs_path)
        try:
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(abs_path, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            raise InfraError(f"could not write image '{path}': {exc}") from exc
        return abs_path

    def exists(self, path: str) -> bool:
        return bool(path) and os.path.isfile(path)

    @staticmethod
    def _mime_for(path: str) -> str:
        _, ext = os.path.splitext(path)
        return _MIME_BY_EXT.get(ext.lower(), "application/octet-stream")
