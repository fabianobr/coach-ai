# Contributing to coach-ai

Thank you for your interest in contributing!

**Before writing any code, read [`AGENTS.md`](AGENTS.md).** It is the canonical
reference for architecture, conventions, MUST rules, and testing patterns. This
file summarises the most common contributor workflows.

## Prerequisites

- **Python ≥ 3.12** — check with `python --version`
- **git**

## Setting Up the Environment

```bash
git clone <repo-url>
cd coach-ai

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install a provider SDK + dev tools
# The dev extra does NOT include any provider SDK — install both together.
pip install -e ".[anthropic,dev]"   # or: openai,dev | ollama,dev | gemini,dev | all,dev

# Copy the example env file and fill in your keys
cp .env.example .env
```

## Running Tests

No API keys are needed — all provider SDKs are mocked.

```bash
pytest tests/ -v                                          # full suite
pytest tests/test_llm_factory.py -v                       # single module
pytest tests/test_llm_providers.py::TestAnthropicProvider -v  # single class
```

## Linting

```bash
ruff check src/ tests/    # report issues
ruff format src/ tests/   # auto-format
```

CI does not exist yet; run both locally before opening a PR.

## Commit Style

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Discord bot runtime
fix: correct tonnage formula for dumbbells
docs: update provider configuration table
test: add TestGeminiProvider class
chore: bump python-telegram-bot to 21.1
```

Allowed types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.

## Pull Request Flow

1. Fork the repo and create a branch from `master`.
2. Make your changes; run `pytest` and `ruff check` before pushing.
3. Open a PR against `master` with a clear description of what changed and why.
4. Reference the relevant section of `AGENTS.md` if your change touches
   architecture, conventions, or the slash command set.

## MUST Rule: Slash Command Sync

If you add or rename a slash command in `.claude/skills/coach/SKILL.md` or
`prompts/SYSTEM_PROMPT.md`, you **must** also update the `/help` and `/start`
handlers in **both** files in the same commit. Failure to do so violates the
project's MUST rules (see `AGENTS.md`).

## Adding a New LLM Provider

The full 6-step process is documented in `AGENTS.md` under
**"Adding a New Provider"**. Short version:

1. Add `src/coach/llm/providers/<name>.py` — subclass `LLMProvider`.
2. Register in `factory.py` (`get_provider`, `_DEFAULT_MODELS`, optionally
   `_key_fallbacks`).
3. Add an optional-dependency group in `pyproject.toml`.
4. Add a `TestXProvider` class in `tests/test_llm_providers.py` following the
   `patch.dict("sys.modules", ...)` pattern.

## Architecture

For a deep-dive into the system design, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
