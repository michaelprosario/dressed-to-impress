"""Unit tests for DressUseCase — no disk, no network."""

from __future__ import annotations

from dressed_to_impress.core.commands.dress_command import DressCommand
from dressed_to_impress.core.use_cases.dress_use_case import DressUseCase
from dressed_to_impress.core.use_cases.prompt_templates import DEFAULT_TRYON_PROMPT
from tests.fakes import FakeImageGenerationProvider, FakeImageRepository

PERSON = "person.png"
OUTFIT = "outfit.png"
OUT = "out.png"


def make_use_case(provider=None, files=None):
    repo = FakeImageRepository(files or {PERSON: b"p", OUTFIT: b"o"})
    provider = provider or FakeImageGenerationProvider()
    return DressUseCase(repo, provider), repo, provider


def command(**overrides):
    base = dict(
        person_image_path=PERSON, outfit_image_path=OUTFIT, output_path=OUT
    )
    base.update(overrides)
    return DressCommand(**base)


def test_happy_path_generates_and_writes():
    use_case, repo, provider = make_use_case()

    result = use_case.execute(command())

    assert result.success
    assert result.value.output_path == OUT
    assert repo.written[OUT] == b"generated"
    # default prompt is used when no override supplied
    assert provider.calls[0][2] == DEFAULT_TRYON_PROMPT


def test_prompt_override_is_passed_through():
    use_case, _, provider = make_use_case()

    use_case.execute(command(prompt_override="make it red"))

    assert provider.calls[0][2] == "make it red"


def test_missing_person_path_is_validation_error():
    use_case, _, _ = make_use_case()

    result = use_case.execute(command(person_image_path=""))

    assert not result.success
    assert any("person image path is required" in e for e in result.validation_errors)


def test_nonexistent_file_is_validation_error():
    use_case, _, _ = make_use_case(files={OUTFIT: b"o"})  # person missing

    result = use_case.execute(command())

    assert not result.success
    assert any("person image not found" in e for e in result.validation_errors)


def test_unsupported_extension_is_validation_error():
    files = {"person.gif": b"p", OUTFIT: b"o"}
    use_case, _, _ = make_use_case(files=files)

    result = use_case.execute(command(person_image_path="person.gif"))

    assert not result.success
    assert any("must be one of" in e for e in result.validation_errors)


def test_unsupported_output_extension_is_validation_error():
    use_case, _, _ = make_use_case()

    result = use_case.execute(command(output_path="out.gif"))

    assert not result.success
    assert any("output path must be one of" in e for e in result.validation_errors)


def test_provider_error_becomes_failure_result():
    provider = FakeImageGenerationProvider(error="safety filtered")
    use_case, repo, _ = make_use_case(provider=provider)

    result = use_case.execute(command())

    assert not result.success
    assert result.message == "safety filtered"
    assert OUT not in repo.written  # nothing written on failure
