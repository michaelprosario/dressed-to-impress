# dressed-to-impress

A Python CLI that dresses a person in an outfit using Gemini ("nano banana")
image generation — a virtual try-on. Given a person image and an outfit image,
the `dress` command produces a photorealistic image of that person wearing the
outfit.

Built following the Clean Architecture rules in
[`prompts/cleanArchitecture.md`](prompts/cleanArchitecture.md); see
[`cliPlan.md`](cliPlan.md) for the full design.

---

## Getting started (step by step)

New to Python projects? Follow these steps in order. Each one is safe to copy and
paste into your terminal.

### 1. Check your prerequisites

You need **Python 3.10 or newer** and **git**. Check what you have:

```bash
python3 --version   # should print 3.10 or higher
git --version
```

If `python3` is missing or too old, install it from
[python.org/downloads](https://www.python.org/downloads/).

### 2. Get the code

```bash
git clone <this-repository-url>
cd dressed-to-impress
```

### 3. Create a virtual environment

A virtual environment keeps this project's packages separate from the rest of your
system. Create one and "activate" it:

```bash
python3 -m venv .venv          # creates a .venv/ folder (one time only)
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows (PowerShell)
```

After activating, your prompt shows `(.venv)`. Re-run the `activate` line each time
you open a new terminal. To leave the environment later, run `deactivate`.

### 4. Install the project

This installs the CLI and its dependencies. The `-e` flag means "editable" — your
code changes take effect without reinstalling.

```bash
pip install -e ".[dev]"
```

To confirm it worked:

```bash
dress --help
```

### 5. Get a Gemini API key

The tool calls Google's Gemini model, which needs an API key (think of it as a
password that lets the tool use your Google account's quota).

1. Go to [Google AI Studio](https://aistudio.google.com/apikey).
2. Sign in with a Google account.
3. Click **Create API key** and copy the value.

> Keep this key private — don't commit it to git or share it.

### 6. Tell the tool your key

The CLI reads the key from an environment variable named `GEMINI_API_KEY`:

```bash
export GEMINI_API_KEY="paste-your-key-here"
```

This lasts only for the current terminal session. To avoid re-typing it, add that
line to your shell profile (`~/.bashrc` or `~/.zshrc`) and restart your terminal.

### 7. Run it

Point the tool at a photo of a person and a photo of an outfit:

```bash
dress --person ./me.jpg --outfit ./jacket.png --out ./me-in-jacket.png
```

On success you'll see:

```
✓ saved: /full/path/to/me-in-jacket.png
```

Open that file to see the result. That's it! 🎉

---

## Command reference

```bash
dress --person PERSON --outfit OUTFIT [--out OUT] [--prompt PROMPT]
```

| Option      | Required | Description                                                        |
| ----------- | -------- | ------------------------------------------------------------------ |
| `--person`  | yes      | Path to the person image.                                          |
| `--outfit`  | yes      | Path to the outfit image.                                          |
| `--out`     | no       | Output path. Defaults to `<person>-dressed.png`.                   |
| `--prompt`  | no       | Override the default instruction sent to Gemini.                   |

Supported image formats: `.png`, `.jpg`, `.jpeg`, `.webp`.

Optional environment variables:

- `GEMINI_API_KEY` (required) — your Gemini API key.
- `DRESS_MODEL` (optional) — override the model, e.g. `gemini-2.5-flash-image-preview`.

Exit codes: `0` success, `1` validation/business failure, `2` configuration error
(e.g. missing API key).

---

## Troubleshooting

| Symptom                                   | Fix                                                                                  |
| ----------------------------------------- | ------------------------------------------------------------------------------------ |
| `dress: command not found`                | Activate your virtual environment (step 3) and reinstall (step 4).                   |
| `error: GEMINI_API_KEY is not set`        | Run the `export GEMINI_API_KEY=...` line from step 6 in this terminal.               |
| `error: person image not found: ...`      | Check the file path; use a path relative to where you're running the command.        |
| `error: ... must be one of .png, .jpg...` | Convert your image to a supported format.                                            |
| `ModuleNotFoundError: No module named 'google'` | Dependencies aren't installed — run `pip install -e ".[dev]"` (step 4).        |

---

## Architecture

```
dressed_to_impress/
├── core/    # business logic: domain, commands, results, ports (interfaces), use case
├── infra/   # adapters: Gemini provider + filesystem repository (implement core ports)
└── cli/     # argparse entry point + composition root (wiring)
```

The `core` package depends on nothing outside itself. `infra` and `cli` depend
inward on `core`.

## Running the tests

```bash
pytest
```

Core tests run with in-memory fakes — no network or disk required.
