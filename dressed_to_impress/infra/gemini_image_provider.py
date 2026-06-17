"""Gemini ("nano banana") implementation of the ImageGenerationProvider port.

Wraps the google-genai SDK. The model accepts multiple input images plus a text
instruction and returns generated image bytes inline. See the nano-banana recipes
code lab referenced in cliPlan.md.
"""

from __future__ import annotations

from ..core.domain.image_asset import ImageAsset
from ..core.ports.errors import InfraError
from ..core.ports.image_generation_provider import ImageGenerationProvider

DEFAULT_MODEL = "gemini-3.1-flash-image"


class GeminiImageProvider(ImageGenerationProvider):
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        # Imported lazily so the Core/test suite need not have google-genai installed.
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate_dressed_image(
        self, person: ImageAsset, outfit: ImageAsset, instruction: str
    ) -> ImageAsset:
        from google.genai import types

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(
                        data=person.data, mime_type=person.mime_type
                    ),
                    types.Part.from_bytes(
                        data=outfit.data, mime_type=outfit.mime_type
                    ),
                    types.Part.from_text(text=instruction),
                ],
            )
        ]
        config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            response_modalities=["TEXT", "IMAGE"],
        )

        try:
            response = self._client.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except Exception as exc:  # SDK raises a variety of types
            raise InfraError(f"Gemini request failed: {exc}") from exc

        image = self._extract_image(response)
        if image is None:
            raise InfraError(
                "Gemini returned no image (the request may have been "
                "safety-filtered or the model produced text only)."
            )
        return image

    @staticmethod
    def _extract_image(response) -> ImageAsset | None:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    mime = getattr(inline, "mime_type", None) or "image/png"
                    return ImageAsset(data=inline.data, mime_type=mime)
        return None
