"""DressUseCase — orchestrates the virtual try-on.

Depends only on the Core ports (constructor-injected). Contains no I/O and no
SDK references, so it is unit-testable with fakes.
"""

from __future__ import annotations

from ..commands.dress_command import DressCommand
from ..ports.errors import InfraError
from ..ports.image_generation_provider import ImageGenerationProvider
from ..ports.image_repository import ImageRepository
from ..results.app_result import AppResult
from ..results.dress_result import DressResult
from .prompt_templates import DEFAULT_TRYON_PROMPT

SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


class DressUseCase:
    def __init__(
        self, repo: ImageRepository, provider: ImageGenerationProvider
    ) -> None:
        self._repo = repo
        self._provider = provider

    def execute(self, cmd: DressCommand) -> AppResult[DressResult]:
        errors = self._validate(cmd)
        if errors:
            return AppResult.invalid(errors)

        try:
            person = self._repo.read(cmd.person_image_path)
            outfit = self._repo.read(cmd.outfit_image_path)
            instruction = cmd.prompt_override or DEFAULT_TRYON_PROMPT
            generated = self._provider.generate_dressed_image(
                person, outfit, instruction
            )
            saved_path = self._repo.write(cmd.output_path, generated.data)
        except InfraError as exc:
            return AppResult.failure(str(exc))

        return AppResult.ok(DressResult(saved_path), "Image generated.")

    def _validate(self, cmd: DressCommand) -> list[str]:
        errors: list[str] = []

        for label, path in (
            ("person", cmd.person_image_path),
            ("outfit", cmd.outfit_image_path),
        ):
            if not path or not path.strip():
                errors.append(f"{label} image path is required")
                continue
            if not self._repo.exists(path):
                errors.append(f"{label} image not found: {path}")
            elif not path.lower().endswith(SUPPORTED_EXTENSIONS):
                errors.append(
                    f"{label} image must be one of {', '.join(SUPPORTED_EXTENSIONS)}: {path}"
                )

        if not cmd.output_path or not cmd.output_path.strip():
            errors.append("output path is required")
        elif not cmd.output_path.lower().endswith(SUPPORTED_EXTENSIONS):
            errors.append(
                f"output path must be one of {', '.join(SUPPORTED_EXTENSIONS)}: "
                f"{cmd.output_path}"
            )

        return errors
