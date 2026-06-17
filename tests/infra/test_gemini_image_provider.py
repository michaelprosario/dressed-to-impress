"""Tests for GeminiImageProvider response parsing (no real SDK client)."""

from __future__ import annotations

from types import SimpleNamespace

from dressed_to_impress.infra.gemini_image_provider import GeminiImageProvider


def _response(parts):
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts))
    return SimpleNamespace(candidates=[candidate])


def test_extract_image_returns_first_inline_image():
    text_part = SimpleNamespace(inline_data=None)
    image_part = SimpleNamespace(
        inline_data=SimpleNamespace(data=b"png-bytes", mime_type="image/png")
    )
    response = _response([text_part, image_part])

    asset = GeminiImageProvider._extract_image(response)

    assert asset is not None
    assert asset.data == b"png-bytes"
    assert asset.mime_type == "image/png"


def test_extract_image_returns_none_when_text_only():
    response = _response([SimpleNamespace(inline_data=None)])

    assert GeminiImageProvider._extract_image(response) is None


def test_extract_image_handles_no_candidates():
    assert GeminiImageProvider._extract_image(SimpleNamespace(candidates=[])) is None
