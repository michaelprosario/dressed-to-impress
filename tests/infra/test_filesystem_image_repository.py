"""Tests for FilesystemImageRepository against a temp directory."""

from __future__ import annotations

import os

import pytest

from dressed_to_impress.core.ports.errors import InfraError
from dressed_to_impress.infra.filesystem_image_repository import (
    FilesystemImageRepository,
)


def test_read_returns_bytes_and_mime(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"hello")
    repo = FilesystemImageRepository()

    asset = repo.read(str(img))

    assert asset.data == b"hello"
    assert asset.mime_type == "image/jpeg"


def test_read_missing_raises_infra_error():
    repo = FilesystemImageRepository()
    with pytest.raises(InfraError):
        repo.read("/no/such/file.png")


def test_write_creates_parent_dirs_and_returns_abspath(tmp_path):
    repo = FilesystemImageRepository()
    target = tmp_path / "nested" / "out.png"

    returned = repo.write(str(target), b"data")

    assert returned == os.path.abspath(str(target))
    assert target.read_bytes() == b"data"


def test_exists(tmp_path):
    repo = FilesystemImageRepository()
    img = tmp_path / "x.png"
    img.write_bytes(b"x")

    assert repo.exists(str(img))
    assert not repo.exists(str(tmp_path / "missing.png"))
