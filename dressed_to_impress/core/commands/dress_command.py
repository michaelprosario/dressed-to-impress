"""Input object for the dress use case (Command pattern).

Core services take command objects as input rather than loose parameters, per the
Clean Architecture rules in prompts/cleanArchitecture.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DressCommand:
    person_image_path: str
    outfit_image_path: str
    output_path: str
    prompt_override: str | None = None
