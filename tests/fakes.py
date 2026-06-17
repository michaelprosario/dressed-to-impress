"""In-memory fakes used to unit-test the Core without disk or network."""

from __future__ import annotations

from dressed_to_impress.core.domain.image_asset import ImageAsset
from dressed_to_impress.core.ports.errors import InfraError
from dressed_to_impress.core.ports.image_generation_provider import (
    ImageGenerationProvider,
)
from dressed_to_impress.core.ports.image_repository import ImageRepository


class FakeImageRepository(ImageRepository):
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files: dict[str, bytes] = dict(files or {})
        self.written: dict[str, bytes] = {}

    def read(self, path: str) -> ImageAsset:
        if path not in self.files:
            raise InfraError(f"missing: {path}")
        return ImageAsset(self.files[path], "image/png", source_path=path)

    def write(self, path: str, data: bytes) -> str:
        self.written[path] = data
        return path

    def exists(self, path: str) -> bool:
        return path in self.files


class FakeImageGenerationProvider(ImageGenerationProvider):
    def __init__(self, result: bytes = b"generated", error: str | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[ImageAsset, ImageAsset, str]] = []

    def generate_dressed_image(
        self, person: ImageAsset, outfit: ImageAsset, instruction: str
    ) -> ImageAsset:
        self.calls.append((person, outfit, instruction))
        if self._error:
            raise InfraError(self._error)
        return ImageAsset(self._result, "image/png")
