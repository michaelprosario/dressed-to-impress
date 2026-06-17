"""`dress` CLI — composition root.

Parses arguments, reads configuration, wires concrete infrastructure into the use
case, and maps the AppResult to stdout/stderr and an exit code. Contains no
business logic.
"""

from __future__ import annotations

import argparse
import os
import sys

from ..core.commands.dress_command import DressCommand
from ..core.use_cases.dress_use_case import DressUseCase
from ..infra.filesystem_image_repository import FilesystemImageRepository
from ..infra.gemini_image_provider import GeminiImageProvider

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_CONFIG = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dress",
        description="Generate an image of a person wearing an outfit (Gemini virtual try-on).",
    )
    parser.add_argument("--person", required=True, help="path to the person image")
    parser.add_argument("--outfit", required=True, help="path to the outfit image")
    parser.add_argument(
        "--out",
        help="output image path (default: <person>-dressed.png next to the person image)",
    )
    parser.add_argument(
        "--prompt", help="override the default try-on instruction sent to Gemini"
    )
    return parser


def default_output_path(person_path: str) -> str:
    root, _ = os.path.splitext(person_path)
    return f"{root}-dressed.png"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY is not set", file=sys.stderr)
        return EXIT_CONFIG

    model = os.environ.get("DRESS_MODEL")

    repo = FilesystemImageRepository()
    provider = (
        GeminiImageProvider(api_key, model=model)
        if model
        else GeminiImageProvider(api_key)
    )
    use_case = DressUseCase(repo, provider)

    command = DressCommand(
        person_image_path=args.person,
        outfit_image_path=args.outfit,
        output_path=args.out or default_output_path(args.person),
        prompt_override=args.prompt,
    )

    result = use_case.execute(command)

    if result.success:
        print(f"✓ saved: {result.value.output_path}")
        return EXIT_OK

    for err in result.validation_errors:
        print(f"error: {err}", file=sys.stderr)
    if result.message:
        print(f"error: {result.message}", file=sys.stderr)
    return EXIT_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
