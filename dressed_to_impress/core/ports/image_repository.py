"""Port for reading/writing images. Implemented by Infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.image_asset import ImageAsset


class ImageRepository(ABC):
    @abstractmethod
    def read(self, path: str) -> ImageAsset:
        """Load an image from `path`. Raises InfraError on failure."""

    @abstractmethod
    def write(self, path: str, data: bytes) -> str:
        """Persist `data` to `path`. Returns the final (absolute) path."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """True if `path` points to a readable file."""
