# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MUST Rules

- **When asked to review, only report findings — never proactively apply fixes.** Present suggestions and wait for explicit instruction before making any changes.
- **Every new slash command added to `SKILL.md` or `SYSTEM_PROMPT.md` must also be listed in the `/help` and `/start` handlers in both files.** Update those handlers as part of the same change — never add a command without registering it there.
- **All architecture diagrams must use Mermaid format.** No ASCII art, Graphviz, or other diagram formats in documentation. This includes: C4 models, sequence diagrams, state diagrams, class diagrams, flowcharts, and data flow diagrams. See `docs/ARCHITECTURE.md` for examples.

## Project Overview

**coach-ai** is a dual-role virtual coach that:
1. **Tracks gym workouts** — dynamic training programs (configurable days), tonnage calculation, progressive overload, PR detection
2. **Corrects English** — every interaction starts with a "Language Spotter" block fixing the user's grammar/vocabulary

The full AI behavior is defined in `prompts/SYSTEM_PROMPT.md`. The Claude Code skill is in `.claude/skills/coach/SKILL.md`.

## Commands

Requires **Python ≥ 3.12**. The `[dev]` extra does not include a provider SDK — install both together:

```bash
# Install a provider + dev tools in one command (Python ≥ 3.12 required)
pip install -e ".[anthropic,dev]"   # or: openai,dev | ollama,dev | gemini,dev | all,dev

# Setup config (required before running tests or commands)
cp .env.example .env                 # fill in API keys if testing live providers

# Run tests (no API keys needed — all SDKs are mocked)
pytest tests/ -v
pytest tests/test_llm_factory.py -v          # single module
pytest tests/test_llm_providers.py::TestAnthropicProvider -v  # single class

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

## Architecture

coach-ai runs in **three independent runtimes**:

1. **Claude Code skill** — `.claude/skills/coach/SKILL.md` loads `prompts/SYSTEM_PROMPT.md` and the active program from `data/programs/` to deliver the full dual-role coaching experience directly inside Claude Code.

2. **Telegram bot** (`src/coach/telegram/`) — production entry point. Loads the active program at startup, injects a `## CURRENT PROGRAM SNAPSHOT` block into the system prompt, and handles all slash commands.

3. **REST API** (`src/coach/api/`) — FastAPI service (`python -m coach.api`). Exposes a `/chat` endpoint backed by the same LLM abstraction layer.

A **CLI** (`python -m coach`) also exists for local interactive use, but does not yet inject the program snapshot into the system prompt.

### LLM Abstraction Layer (`src/coach/llm/`)

Provider-agnostic design — swap providers via `.env`, no code changes needed.

- **`base.py`** — `LLMProvider` ABC with `chat()` and `stream()` methods; `Message` and `LLMConfig` dataclasses
- **`factory.py`** — `get_provider(config?)` instantiates the right provider; `config_from_env()` reads `.env`
- **`providers/`** — one file per provider; `ollama.py` is a thin wrapper that delegates to `OpenAIProvider` pointed at `http://localhost:11434/v1`

All providers implement the same interface:

```python
from coach.llm import get_provider, Message

llm = get_provider()  # reads LLM_PROVIDER from .env
response = llm.chat([Message(role="user", content="squat done 5x5")])

for chunk in llm.stream([Message(role="user", content="bench cues?")]):
    print(chunk, end="", flush=True)
```

### Adding a new provider

1. Create `src/coach/llm/providers/<name>.py` — subclass `LLMProvider`, implement `chat()` and `stream()`.
2. Add a `case "<name>":` branch in `get_provider()` (`src/coach/llm/factory.py:71`).
3. Add a default model to `_DEFAULT_MODELS` (`factory.py:8`).
4. If an API key falls back to a vendor env var, add it to `_key_fallbacks` (`factory.py:35`).
5. Add an optional-dependency group in `pyproject.toml` under `[project.optional-dependencies]`.
6. Add a `TestXProvider` class in `tests/test_llm_providers.py` — mock the SDK with `patch.dict("sys.modules", ...)` and import the provider **inside** the context (same pattern as existing classes).

### Provider Configuration (`.env`)

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `ollama` \| `gemini` |
| `LLM_MODEL` | *(see defaults below)* | Leave blank to use provider default |
| `LLM_API_KEY` | — | Falls back to `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` |
| `LLM_BASE_URL` | — | Useful for Ollama (`http://localhost:11434/v1`) or proxies |
| `LLM_MAX_TOKENS` | `2048` | |
| `LLM_TEMPERATURE` | `0.7` | |

Default models: `anthropic` → `claude-haiku-4-5-20251001`, `openai` → `gpt-4o-mini`, `ollama` → `llama3.2`, `gemini` → `gemini-2.0-flash`.

### Training Programs (`data/programs/`)

Programs are stored as JSON files in `data/programs/`. The active program is identified by `data/programs/active.txt`.

Manage programs with:
- `/programs` — list all programs
- `/program show [id]` — view a program
- `/program switch <id>` — activate a program
- `/program clone <src> <dst>` — copy a program (then hand-edit the JSON)

Tonnage formulas (from `program.barbell_weight_kg` in the active program file):
- **Barbell:** `(weight_per_side × 2 + barbell_weight_kg) × reps × sets`
- **Machine/cable/dumbbell:** `weight × reps × sets`
- **Isometric:** track as TuT (seconds), no tonnage

## Testing

Tests use `unittest.mock` and `patch.dict("sys.modules", ...)` to mock provider SDKs. No real API calls are made.

**Critical:** Place `isinstance` assertions and `from ... import` statements **inside** the `patch.dict` context — not after it exits. Exiting the context flushes the module cache, causing class identity mismatches.

Tests import via `from src.coach.llm... import ...` (e.g. `tests/test_llm_providers.py:6`), not `from coach.llm...`. Keep that pattern when adding new tests — it's tied to the `patch.dict` mocking setup.

## Conventions

- All output in **English**
- Missing data → `"N/A"`, never invented
- Isometric exercises tracked by TuT (seconds), not tonnage
- Logs saved to `logs/YYYY-MM-DD.md` (git-ignored)
- Conventional Commits: `feat:`, `fix:`, `chore:`, `test:`

## Next Steps (In Development)

- **PR detection cross-program** — `logger.detect_prs()` scans all prior logs regardless of program. Filter by `program_id` (already written to the Session Overview table) to avoid flagging a weight PR that belongs to a different program.
- **CLI slash commands** — `/day`, `/programs`, `/program switch` etc. are only wired in the Telegram bot. A thin command dispatcher in `cli.py` would make the CLI a full-featured alternative to Telegram.

## Dev Notes

**After removing a git worktree**, run `pip install -e ".[anthropic,dev]"` from the repo root. The editable install's `.pth` file records the worktree's `src/` path; once the worktree is deleted, `import coach` breaks until reinstalled.
