"""Port for the image-generation backend. Implemented by Infrastructure."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.image_asset import ImageAsset


class ImageGenerationProvider(ABC):
    @abstractmethod
    def generate_dressed_image(
        self, person: ImageAsset, outfit: ImageAsset, instruction: str
    ) -> ImageAsset:
        """Generate an image of `person` wearing `outfit`.

        Raises InfraError if generation fails or no image is returned.
        """
