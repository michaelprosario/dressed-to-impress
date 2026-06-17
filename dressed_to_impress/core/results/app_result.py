"""AppResult — the consistent return type for Core services.

Every Core service reports success/failure through this object instead of raising
exceptions for expected business failures (validation, missing input, provider
error). This gives callers a single, easy-to-consume signature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class AppResult(Generic[T]):
    success: bool
    value: T | None = None
    message: str = ""
    validation_errors: list[str] = field(default_factory=list)

    @staticmethod
    def ok(value: T, message: str = "") -> "AppResult[T]":
        return AppResult(success=True, value=value, message=message)

    @staticmethod
    def invalid(errors: list[str]) -> "AppResult[T]":
        return AppResult(success=False, validation_errors=list(errors))

    @staticmethod
    def failure(message: str) -> "AppResult[T]":
        return AppResult(success=False, message=message)
