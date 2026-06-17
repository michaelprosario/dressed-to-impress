# `dress` CLI — Code Plan

A Python CLI that takes a **person image** and an **outfit image** and uses Gemini
("nano banana" image generation) to produce a new image of that person wearing the
outfit (virtual try-on).

The design follows the Clean Architecture rules in
[`prompts/cleanArchitecture.md`](prompts/cleanArchitecture.md): dependencies point
inward, the **Core** owns the business logic and defines interfaces, **Infrastructure**
implements them (Gemini + filesystem), and the **CLI** is a thin outer layer that only
parses input and orchestrates a use case.

---

## 1. Use case (the contract)

```
Given  a path to an outfit image AND a path to a person image
When   I run the `dress` command
Then   the system generates and saves an image of the person wearing the outfit
```

Example:

```bash
dress --person ./me.jpg --outfit ./jacket.png --out ./me-in-jacket.png
```

---

## 2. Requirements

### Functional
- Accept a person image path and an outfit image path as inputs.
- Accept an output path (default: derived name like `<person>-dressed.png` in CWD).
- Read both images from the filesystem.
- Send both images + an instruction prompt to Gemini and get back a generated image.
- Save the generated image to the output path.
- Report success (with output path) or a clear, actionable failure.

### Non-functional / constraints
- **Language/stack:** Python 3.10+, `google-genai` SDK, CLI.
- **Core has zero dependency** on `google-genai`, the filesystem, or `argparse`/`click`.
  It depends only on interfaces it defines.
- Inputs to Core services are **command objects**; outputs are an **AppResult** object
  (no exceptions for expected business failures — validation, missing file, API error).
- Core use case is **unit-testable** with fake providers/repositories (no network, no disk).
- API key supplied via env var (`GEMINI_API_KEY`), never hard-coded.

### Validation rules (handled before any API call)
- Both `person` and `outfit` paths are provided.
- Files exist and are readable.
- Files have a supported image extension (`.png`, `.jpg`, `.jpeg`, `.webp`).
- Output directory is writable.

---

## 3. Project structure

```
dressed_to_impress/
├── core/                         # innermost — pure business logic, no I/O deps
│   ├── domain/
│   │   └── image_asset.py        # ImageAsset value object (bytes + mime_type)
│   ├── ports/                    # interfaces the Core defines, Infra implements
│   │   ├── image_generation_provider.py   # ImageGenerationProvider (ABC)
│   │   └── image_repository.py             # ImageRepository (ABC)
│   ├── commands/
│   │   └── dress_command.py      # DressCommand (input object)
│   ├── results/
│   │   └── app_result.py         # AppResult[T] (success/failure/messages/errors)
│   └── use_cases/
│       └── dress_use_case.py     # DressUseCase — orchestrates the flow
│
├── infra/                        # outermost concerns — implements Core ports
│   ├── gemini_image_provider.py  # ImageGenerationProvider via google-genai
│   └── filesystem_image_repository.py      # ImageRepository via local disk
│
├── cli/
│   ├── main.py                   # argparse entry point, composition root (wiring)
│   └── prompt_templates.py       # default try-on instruction text
│
├── tests/
│   ├── core/
│   │   └── test_dress_use_case.py   # unit tests w/ fakes — no network, no disk
│   └── infra/
│       └── test_filesystem_image_repository.py
│
├── pyproject.toml                # deps + `dress` console_scripts entry point
└── README.md
```

**Dependency direction:** `cli → core` and `infra → core`. The `core` package
imports nothing from `infra` or `cli`. Wiring of concrete classes happens only in
`cli/main.py` (the composition root).

---

## 4. Core components

### 4.1 Domain — `ImageAsset`
A value object holding raw image data the Core can reason about without touching disk.

```python
@dataclass(frozen=True)
class ImageAsset:
    data: bytes
    mime_type: str          # e.g. "image/png"
    source_path: str | None = None
```

### 4.2 Command — `DressCommand` (input to the use case)
```python
@dataclass(frozen=True)
class DressCommand:
    person_image_path: str
    outfit_image_path: str
    output_path: str
    prompt_override: str | None = None   # optional custom instruction
```

### 4.3 Result — `AppResult[T]` (output of every Core service)
Consistent, exception-free signature reporting success/failure + messages.

```python
@dataclass(frozen=True)
class AppResult(Generic[T]):
    success: bool
    value: T | None = None
    message: str = ""
    validation_errors: list[str] = field(default_factory=list)

    @staticmethod
    def ok(value, message="") -> "AppResult": ...
    @staticmethod
    def invalid(errors: list[str]) -> "AppResult": ...
    @staticmethod
    def failure(message: str) -> "AppResult": ...
```

For this use case `T` is a small `DressResult` (`output_path: str`).

### 4.4 Ports (interfaces defined by Core)
```python
class ImageRepository(ABC):
    @abstractmethod
    def read(self, path: str) -> ImageAsset: ...
    @abstractmethod
    def write(self, path: str, data: bytes) -> str: ...     # returns final path
    @abstractmethod
    def exists(self, path: str) -> bool: ...

class ImageGenerationProvider(ABC):
    @abstractmethod
    def generate_dressed_image(
        self, person: ImageAsset, outfit: ImageAsset, instruction: str
    ) -> ImageAsset: ...
```

### 4.5 Use case — `DressUseCase`
Depends only on the two ports (constructor-injected). Pure orchestration:

```python
class DressUseCase:
    def __init__(self, repo: ImageRepository, provider: ImageGenerationProvider):
        self._repo = repo
        self._provider = provider

    def execute(self, cmd: DressCommand) -> AppResult[DressResult]:
        errors = self._validate(cmd)          # paths present, exist, valid ext
        if errors:
            return AppResult.invalid(errors)
        person = self._repo.read(cmd.person_image_path)
        outfit = self._repo.read(cmd.outfit_image_path)
        instruction = cmd.prompt_override or DEFAULT_TRYON_PROMPT
        generated = self._provider.generate_dressed_image(person, outfit, instruction)
        saved_path = self._repo.write(cmd.output_path, generated.data)
        return AppResult.ok(DressResult(saved_path), "Image generated.")
```

Provider/repository failures are translated to `AppResult.failure(...)` (a thin
try/except wrapper around the orchestration, or each adapter raises a typed
`InfraError` the use case catches).

---

## 5. Infrastructure components

### 5.1 `FilesystemImageRepository(ImageRepository)`
- `read`: open file in binary, infer `mime_type` from extension, return `ImageAsset`.
- `write`: create parent dirs if needed, write bytes, return absolute path.
- `exists`: `os.path.isfile`.

### 5.2 `GeminiImageProvider(ImageGenerationProvider)`
Wraps the `google-genai` SDK (per the nano-banana code lab).

```python
from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash-image-preview"   # "nano banana"

class GeminiImageProvider(ImageGenerationProvider):
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)   # AI Studio key
        # (Vertex alt: genai.Client(vertexai=True, project=..., location="global"))

    def generate_dressed_image(self, person, outfit, instruction):
        contents = [types.Content(role="user", parts=[
            types.Part.from_bytes(data=person.data, mime_type=person.mime_type),
            types.Part.from_bytes(data=outfit.data, mime_type=outfit.mime_type),
            types.Part.from_text(text=instruction),
        ])]
        config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"], temperature=1, top_p=0.95,
        )
        resp = self._client.models.generate_content(
            model=MODEL, contents=contents, config=config)
        for part in resp.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                return ImageAsset(part.inline_data.data, "image/png")
        raise InfraError("Gemini returned no image (possibly safety-filtered).")
```

### 5.3 Default prompt — `cli/prompt_templates.py`
```python
DEFAULT_TRYON_PROMPT = (
    "Using the first image as the person and the second image as the outfit, "
    "generate a photorealistic image of the same person wearing that outfit. "
    "Preserve the person's face, body, pose, and background; keep lighting consistent."
)
```

---

## 6. CLI layer — `cli/main.py` (composition root)

Responsibilities only: parse args, read config, build dependencies, call the use case,
map `AppResult` to stdout/stderr + exit code. No business logic.

```python
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dress", description="Virtual try-on via Gemini")
    p.add_argument("--person", required=True, help="path to person image")
    p.add_argument("--outfit", required=True, help="path to outfit image")
    p.add_argument("--out", help="output path (default: <person>-dressed.png)")
    p.add_argument("--prompt", help="override the default instruction")
    return p

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY is not set", file=sys.stderr); return 2

    # wiring — the only place concrete infra is referenced
    repo = FilesystemImageRepository()
    provider = GeminiImageProvider(api_key)
    use_case = DressUseCase(repo, provider)

    cmd = DressCommand(
        person_image_path=args.person,
        outfit_image_path=args.outfit,
        output_path=args.out or default_output_path(args.person),
        prompt_override=args.prompt,
    )
    result = use_case.execute(cmd)

    if result.success:
        print(f"✓ saved: {result.value.output_path}"); return 0
    for e in result.validation_errors:
        print(f"error: {e}", file=sys.stderr)
    if result.message:
        print(f"error: {result.message}", file=sys.stderr)
    return 1
```

Exit codes: `0` success, `1` validation/business failure, `2` config/usage error.

---

## 7. Configuration
- `GEMINI_API_KEY` — required (AI Studio key). Read only in `cli/main.py`.
- Optional future: `DRESS_MODEL` to override the model id, `DRESS_VERTEX_PROJECT`
  to switch to the Vertex client path.

---

## 8. Testing strategy
- **Core (unit, no I/O):** `DressUseCase` tested with a `FakeImageRepository`
  (in-memory dict) and `FakeImageGenerationProvider` (returns canned bytes / raises).
  Cover: happy path, missing path, nonexistent file, bad extension, provider error,
  provider returns no image. Assert on `AppResult` shape — never on side effects.
- **Infra (integration-lite):** `FilesystemImageRepository` against `tmp_path`.
  `GeminiImageProvider` behind a mocked `genai.Client` (no real network in CI).
- **CLI:** invoke `main(["--person", ..., "--outfit", ...])` with fakes injected via a
  small factory seam; assert exit code and stdout/stderr.

---

## 9. Dependencies & packaging (`pyproject.toml`)
- Runtime: `google-genai`, `pillow` (mime/validation helper, optional).
- Dev: `pytest`.
- Console entry point:
  ```toml
  [project.scripts]
  dress = "dressed_to_impress.cli.main:main"
  ```

---

## 10. Build order (suggested)
1. `AppResult`, `ImageAsset`, `DressCommand` (pure data).
2. Ports (`ImageRepository`, `ImageGenerationProvider`).
3. `DressUseCase` + unit tests with fakes (red→green before any infra).
4. `FilesystemImageRepository` + tests.
5. `GeminiImageProvider` (mocked-client test).
6. `cli/main.py` wiring + end-to-end smoke test against real Gemini.
