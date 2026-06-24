# Inside the "Dress" CLI: A Beginner's Guide to Clean Architecture and Gemini Image Generation

Have you ever wondered how to build a professional-grade command-line tool in Python that coordinates advanced AI image generation, handles files, and remains easy to test and expand?

In this post, we'll peel back the layers of the `dress` CLI—a command-line virtual try-on application that lets users select a photo of a person and an outfit, sending them to Google Gemini to generate an image of the person wearing that outfit.

We will focus on the program's "entry point" at [main.py](file:///home/user/dressed-to-impress/dressed_to_impress/cli/main.py) and dive deep into how the **Infrastructure Layer**, **Prompts**, and **Gemini SDK** build the try-on images.

---

## 1. What is Clean Architecture?

Before we look at the code, let's look at the philosophy behind it. This project follows **Clean Architecture**.

The main rule of Clean Architecture is: **Dependencies point inward.**
- **The Core Layer (Innermost)**: Houses the business logic. It does not know about the internet, filesystems, database systems, or command-line frameworks. It only defines interfaces (ports) and use cases.
- **The Infrastructure Layer (Middle)**: Implements these ports. This is where file saving (`FilesystemImageRepository`) and Gemini API calls (`GeminiImageProvider`) live.
- **The CLI Layer (Outermost)**: Interacts with the user, parses arguments, and starts the core execution.

By decoupling the layers, the inner logic becomes independent of frameworks. This is why we were able to deploy this same try-on logic to a Google Cloud Function without modifying a single line of core business logic!

---

## 2. Exploring [main.py](file:///home/user/dressed-to-impress/dressed_to_impress/cli/main.py)

Let's walk through the script step-by-step to see how it operates.

### Step 2.1: The Parsing Engine (`argparse`)
Every good command line tool needs to understand user flags like `--person` or `--outfit`. In Python, the standard library provides `argparse` to handle this:

```python
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
```

- `argparse` automatically generates help menus (`dress --help`).
- It validates that required flags are present and extracts their values.

### Step 2.2: Managing Configuration & Secrets (`dotenv`)
We need an API key to communicate with Google's Gemini models. We store this sensitive key in a `.env` file instead of hardcoding it in the code. We use the `python-dotenv` package to load it:

```python
def load_env() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
```

This searches for a `.env` file upwards from the current directory, reading key-value pairs and loading them directly into operating system environment variables (`os.environ`).

### Step 2.3: The Main Function and "Composition Root"
The `main()` function is the **Composition Root**. It is the only place in the app where concrete infrastructure elements (filesystem repositories and real Gemini providers) are created and wired together:

```python
def main(argv: list[str] | None = None) -> int:
    load_env()
    args = build_parser().parse_args(argv)

    # 1. Configuration Check
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY is not set", file=sys.stderr)
        return EXIT_CONFIG

    model = os.environ.get("DRESS_MODEL")

    # 2. Dependency Injection / Wiring
    repo = FilesystemImageRepository()
    provider = GeminiImageProvider(api_key, model=model) if model else GeminiImageProvider(api_key)
    
    use_case = DressUseCase(repo, provider)

    # 3. Packaging Inputs (Command Pattern)
    command = DressCommand(
        person_image_path=args.person,
        outfit_image_path=args.outfit,
        output_path=args.out or default_output_path(args.person),
        prompt_override=args.prompt,
    )

    # 4. Orchestration
    result = use_case.execute(command)

    # 5. Mapping Results
    if result.success:
        print(f"✓ saved: {result.value.output_path}")
        return EXIT_OK

    for err in result.validation_errors:
        print(f"error: {err}", file=sys.stderr)
    if result.message:
        print(f"error: {result.message}", file=sys.stderr)
    return EXIT_FAILURE
```

---

## 3. The Infrastructure Layer Elements

In Clean Architecture, the **Infrastructure Layer** contains the concrete adapters that connect our Core to external interfaces like local hard drives or remote APIs.

### 3.1 Filesystem Adapter: `FilesystemImageRepository`
Defined in [filesystem_image_repository.py](file:///home/user/dressed-to-impress/dressed_to_impress/infra/filesystem_image_repository.py):
This class handles disk I/O.
- **Reading**: Opens a file in binary mode (`"rb"`), reads raw bytes, and maps the file extension to a MIME type (e.g., `.png` becomes `image/png`).
- **Writing**: Safely creates parent folders if they don't exist and writes generated bytes back to the disk.
- It translates raw operating system errors (`OSError`) into a core-friendly exception: `InfraError`.

### 3.2 AI Service Adapter: `GeminiImageProvider`
Defined in [gemini_image_provider.py](file:///home/user/dressed-to-impress/dressed_to_impress/infra/gemini_image_provider.py):
This is the bridge to the Google Gemini API. It encapsulates the `google-genai` SDK, so that the inner layers remain untouched by external API upgrades.

---

## 4. Prompt Engineering: Guiding the Model

How do we instruct an AI model to generate a virtual try-on image? We use carefully crafted instructions (prompts) inside the Core layer.

Defined in [prompt_templates.py](file:///home/user/dressed-to-impress/dressed_to_impress/core/use_cases/prompt_templates.py):
```python
DEFAULT_TRYON_PROMPT = (
    "Using the first image as the person and the second image as the outfit, "
    "generate a photorealistic image of the same person wearing that outfit. "
    "Preserve the person's face, body shape, pose, and background; keep the "
    "lighting and perspective consistent and natural."
)
```

### Why does this prompt work?
- **Ordering Instruction**: Explicitly states which image is which ("first image as the person", "second image as the outfit").
- **Constraints**: Instructs the model on what **not** to change ("Preserve the person's face, body shape, pose, and background"). This maintains identity consistency.
- **Style Direction**: Controls lighting and perspective consistency to prevent artificial overlays or cartoon styles.

---

## 5. Image Building with Gemini

Let's look at how the `google-genai` SDK is used inside [gemini_image_provider.py](file:///home/user/dressed-to-impress/dressed_to_impress/infra/gemini_image_provider.py) to synthesize multimodal images.

### Step 5.1: Assembling Multimodal Input (Parts)
The Gemini model accepts lists of **Parts**. A Part can be text, an image, or a video. We compile both input images and the prompt text into a single payload:
```python
from google.genai import types

contents = [
    types.Content(
        role="user",
        parts=[
            types.Part.from_bytes(data=person.data, mime_type=person.mime_type),
            types.Part.from_bytes(data=outfit.data, mime_type=outfit.mime_type),
            types.Part.from_text(text=instruction),
        ]
    )
]
```

### Step 5.2: Configuring Image Generation Modalities
To instruct Gemini to output a physical image alongside text (multimodal response), we specify `"IMAGE"` inside the configuration modalities:
```python
config = types.GenerateContentConfig(
    temperature=1,
    top_p=0.95,
    response_modalities=["TEXT", "IMAGE"],
)
```

### Step 5.3: Parsing the API Response
Gemini returns a complex response structure. The generated image bytes are returned in the response parts as `inline_data`. We traverse the response to extract it:
```python
candidates = getattr(response, "candidates", None) or []
for candidate in candidates:
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None) or []
    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            mime = getattr(inline, "mime_type", None) or "image/png"
            return ImageAsset(data=inline.data, mime_type=mime)
```
Once extracted, the raw bytes are returned as a domain-level `ImageAsset` for clean use by Core Use Cases.

---

## 6. Summary

Building a clean application is about establishing boundaries:
1. The **CLI** parses user input and configures dependencies.
2. Concrete **Adapters** in `infra` handle the details of filesystems and APIs.
3. The **Core Usecase** orchestrates the business flow purely through abstract interfaces.
4. **Gemini Multimodal inputs** make AI operations as simple as building byte lists and text instructions.

By isolating these concerns, your code remains clean, easy to read, testable, and ready to adapt to whatever changes come tomorrow. Happy coding!
