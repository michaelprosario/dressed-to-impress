"""Successful payload of the dress use case."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DressResult:
    output_path: str
