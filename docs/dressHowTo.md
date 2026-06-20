# Inside the "Dress" CLI: A Beginner's Guide to Clean Architecture in Python

Have you ever wondered how to build a professional-grade command-line tool in Python that coordinates advanced AI image generation, handles files, and remains easy to test and expand?

In this post, we'll peel back the layers of the `dress` CLI—a command-line virtual try-on application that lets users select a photo of a person and an outfit, sending them to Google Gemini to generate an image of the person wearing that outfit.

We will focus on the program's "entry point" at [main.py](file:///home/user/dressed-to-impress/dressed_to_impress/cli/main.py) and explore the concepts that make this codebase clean, modular, and robust.

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

## 3. Key Programming Concepts to Master

As a Python developer, mastering the following concepts used in this program will elevate the quality of your code:

### Concept 3.1: Dependency Injection (DI)
Notice how `DressUseCase` does not instantiate `FilesystemImageRepository` or `GeminiImageProvider` inside its constructor. Instead, they are passed (injected) into it:
```python
use_case = DressUseCase(repo, provider)
```
This is **Dependency Injection**. Because `DressUseCase` only cares that `repo` and `provider` conform to interfaces, we can swap them out for `FakeImageRepository` and `FakeImageProvider` in unit tests, allowing us to test our business logic in milliseconds without touching a real disk or making network calls to Gemini!

### Concept 3.2: The Command Pattern
Instead of passing loose arguments like `execute(person, outfit, output_path, prompt)`, we bundle them into a single, immutable data object called `DressCommand`.
This guarantees structure, validation consistency, and makes it easy to add future parameters without changing method signatures.

### Concept 3.3: The AppResult Pattern
Instead of raising and catching complex exceptions for anticipated validation or server errors, core services always return an `AppResult` object.
The result payload clearly tells the CLI whether the operation was a success or failure, along with error lists:
```python
if result.success:
    # do success action
else:
    # print validation_errors / failure message
```
This leads to safer flow control and simplifies how delivery frameworks (like our CLI or Cloud Functions) render outcomes to the screen or API responses.

---

## 4. Summary

Building a clean application is about establishing boundaries:
1. The **CLI** parses user input and configures dependencies.
2. Concrete **Adapters** in `infra` handle the details of filesystems and APIs.
3. The **Core Usecase** orchestrates the business flow purely through abstract interfaces.

By isolating these concerns, your code remains clean, easy to read, testable, and ready to adapt to whatever changes come tomorrow. Happy coding!
