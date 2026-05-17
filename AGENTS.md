# AGENTS.md — coach-ai project rules

Rules, architecture, and conventions for **every AI coding assistant** working in
this repository (Claude Code, Cline, Continue, Copilot, etc.).

> **Claude Code** reads this file via `@AGENTS.md` in `CLAUDE.md`.
> **Cline** reads `.clinerules/coach-ai.md`, which points here.
> **Continue** reads `.continue/rules/coach-ai.md`, which points here.

---

## MUST Rules

These rules override any default assistant behavior and apply to all tools.

1. **Review = report only.** When asked to review code, report findings and wait
   for explicit instruction. Never apply fixes proactively.

2. **Slash command sync.** Every new slash command added to
   `.claude/skills/coach/SKILL.md` or `prompts/SYSTEM_PROMPT.md` must also be
   listed in the `/help` and `/start` handlers in **both** files. Update those
   handlers in the same change — never add a command without registering it there.

3. **Mermaid-only diagrams.** All architecture diagrams must use Mermaid format.
   No ASCII art, Graphviz, or other formats. This applies to C4 models, sequence
   diagrams, state diagrams, class diagrams, flowcharts, and data flow diagrams.
   See `docs/ARCHITECTURE.md` for examples.

---

## Project Overview

**coach-ai** is a dual-role virtual coach:

- **Gym tracker** — logs workouts on a dynamic training program (configurable
  days), calculates tonnage, detects PRs, and suggests progressive overload.
- **English coach** — every user interaction begins with a "Language Spotter"
  block that corrects grammar and vocabulary.

The full AI behavior is defined in `prompts/SYSTEM_PROMPT.md`. The Claude Code
skill entry point is `.claude/skills/coach/SKILL.md`.

---

## Repository Layout

```
coach-ai/
├── AGENTS.md                     # This file — canonical project rules
├── CLAUDE.md                     # Claude Code pointer → AGENTS.md
├── CONTRIBUTING.md               # Contributor guide
├── LICENSE                       # MIT
├── README.md                     # Quick start for all audiences
├── pyproject.toml
├── .env.example                  # Copy to .env and fill in keys
├── .clinerules/coach-ai.md       # Cline pointer → AGENTS.md
├── .continue/rules/coach-ai.md   # Continue pointer → AGENTS.md
│
├── prompts/
│   └── SYSTEM_PROMPT.md          # Runtime AI behavior definition (all runtimes)
│
├── data/programs/
│   ├── active.txt                # Active program ID (e.g. "powerbuilding-4d")
│   └── <program_id>.json         # Training program definitions
│
├── src/coach/
│   ├── __main__.py               # CLI entry point (python -m coach)
│   ├── cli.py                    # CoachCLI — interactive loop
│   ├── day_plan.py               # Day plan formatting helpers
│   ├── logger.py                 # Session log writer (logs/YYYY-MM-DD.md)
│   ├── paths.py                  # Centralised resource path resolution
│   ├── programs.py               # Program loader and active-program management
│   ├── llm/                      # LLM abstraction layer (see below)
│   ├── api/                      # FastAPI REST service (python -m coach.api)
│   └── telegram/                 # Telegram bot (python -m coach.telegram)
│
├── tests/                        # pytest test suite
│   └── fixtures/programs/        # Isolated program fixtures for tests
│
├── docs/
│   ├── ARCHITECTURE.md           # C4 diagrams, sequence diagrams, design decisions
│   ├── TELEGRAM_BOT_SETUP.md     # Telegram deployment guide
│   └── API_GUIDE.md              # REST API endpoint reference
│
├── scripts/
│   ├── start_telegram_bot.py     # Verified launch script (cross-platform)
│   └── start_telegram_bot.sh     # Bash launch script (macOS/Linux)
│
└── logs/                         # Session logs — git-ignored
```

---

## The Four Runtimes

All runtimes share the same LLM abstraction layer and load `.env` via
`python-dotenv`. Each requires its own dependency extras.

| Runtime | Command | Required extras |
| :-- | :-- | :-- |
| Claude Code skill | Open repo in Claude Code; `coach` activates automatically | — (no Python needed) |
| CLI | `python -m coach` | `anthropic` (or any provider) + `dev` |
| REST API | `python -m coach.api` | `rest` + provider |
| Telegram bot | `python -m coach.telegram` | `telegram` + provider |

Helper scripts for the Telegram bot:

```bash
python scripts/start_telegram_bot.py   # recommended — validates env first
./scripts/start_telegram_bot.sh        # bash equivalent
```

The REST API listens on `HOST` (default `127.0.0.1`) and `PORT` (default `8000`).
See `docs/API_GUIDE.md` for endpoint reference.

---

## LLM Abstraction Layer (`src/coach/llm/`)

Provider-agnostic design — swap providers by changing `.env`, no code changes needed.

```
src/coach/llm/
├── __init__.py       # Re-exports: LLMConfig, LLMProvider, Message, get_provider, config_from_env
├── base.py           # LLMProvider ABC; Message and LLMConfig dataclasses
├── factory.py        # get_provider() — instantiates the right provider from config
└── providers/
    ├── anthropic.py  # AnthropicProvider
    ├── openai.py     # OpenAIProvider
    ├── ollama.py     # OllamaProvider (thin wrapper over OpenAIProvider)
    └── gemini.py     # GeminiProvider
```

All providers implement the same interface:

```python
from coach.llm import get_provider, Message

llm = get_provider()          # reads LLM_PROVIDER from .env
response = llm.chat([Message(role="user", content="squat done 5x5")])

for chunk in llm.stream([Message(role="user", content="bench cues?")]):
    print(chunk, end="", flush=True)
```

For a deep-dive into the architecture see `docs/ARCHITECTURE.md`.

### Adding a New Provider

1. Create `src/coach/llm/providers/<name>.py` — subclass `LLMProvider`,
   implement `chat()` and `stream()`.
2. Add a `case "<name>":` branch in `get_provider()` (`src/coach/llm/factory.py`).
3. Add a default model to `_DEFAULT_MODELS` in `factory.py`.
4. If the provider has a vendor API-key env var, add it to `_key_fallbacks` in
   `factory.py`.
5. Add an optional-dependency group in `pyproject.toml` under
   `[project.optional-dependencies]`.
6. Add a `TestXProvider` class in `tests/test_llm_providers.py` — mock the SDK
   with `patch.dict("sys.modules", ...)` and import the provider **inside** the
   context (same pattern as existing classes).

---

## Provider Configuration (`.env`)

Copy `.env.example` to `.env` and fill in the values.

| Variable | Default | Notes |
| :-- | :-- | :-- |
| `LLM_PROVIDER` | `anthropic` | `anthropic` \| `openai` \| `ollama` \| `gemini` |
| `LLM_MODEL` | *(see defaults)* | Leave blank to use the provider default |
| `LLM_API_KEY` | — | Falls back to `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` |
| `LLM_BASE_URL` | — | Useful for Ollama (`http://localhost:11434/v1`) or proxies |
| `LLM_MAX_TOKENS` | `2048` | |
| `LLM_TEMPERATURE` | `0.7` | |
| `TELEGRAM_BOT_TOKEN` | — | Required for the Telegram runtime |
| `HOST` | `127.0.0.1` | Bind address for the REST API |
| `PORT` | `8000` | Port for the REST API |

Default models: `anthropic` → `claude-haiku-4-5-20251001`, `openai` → `gpt-4o-mini`,
`ollama` → `llama3.2`, `gemini` → `gemini-2.0-flash`.

**Using a local LLM (e.g. Qwen via Ollama):**

```bash
ollama pull qwen2.5:7b
# In .env:
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434/v1
```

---

## Training Programs (`data/programs/`)

Programs are JSON files in `data/programs/`. The active program is identified by
the ID stored in `data/programs/active.txt`.

Manage programs via slash commands (Telegram bot or Claude Code skill):

| Command | Action |
| :-- | :-- |
| `/programs` | List all programs (active one marked ✅) |
| `/program show [id]` | View a program (defaults to active) |
| `/program switch <id>` | Activate a program |
| `/program clone <src> <dst>` | Copy a program; hand-edit the JSON |

**Tonnage formulas** (driven by `program.barbell_weight_kg` in the JSON):

- Barbell: `(weight_per_side × 2 + barbell_weight_kg) × reps × sets`
- Machine / cable / dumbbell: `weight × reps × sets`
- Isometric: track as TuT (seconds) — no tonnage

---

## Conventions

- **Output language:** English for all code, comments, docs, and logs.
- **Missing data:** use `"N/A"`, never invent values.
- **Isometric exercises:** tracked by TuT (seconds), not tonnage.
- **Session logs:** written to `logs/YYYY-MM-DD.md` (git-ignored).
- **Commit style:** Conventional Commits — `feat:`, `fix:`, `chore:`, `test:`, `docs:`.
- **Line length:** 100 characters (enforced by ruff).
- **Python target:** 3.12+.

---

## Testing Conventions

Tests use `unittest.mock` and `patch.dict("sys.modules", ...)` to mock provider
SDKs. No real API calls are made — no keys needed to run the suite.

**Critical pattern:** place `isinstance` assertions and `from ... import`
statements **inside** the `patch.dict` context — never after it exits. Exiting
the context flushes the module cache, causing class-identity mismatches.

Import paths in tests use `from src.coach.llm... import ...` (not
`from coach.llm...`). Keep that pattern when adding new tests — it's tied to
the `patch.dict` mocking setup.

The test fixture in `conftest.py` copies `tests/fixtures/programs/` into a
per-test `tmp_path` and sets `COACH_PROGRAMS_DIR_PATH` and
`COACH_LOGS_DIR_PATH`, giving each test an isolated, mutable program directory.

---

## Commands

```bash
# Install (Python >= 3.12 required; pick a provider extra + dev)
pip install -e ".[anthropic,dev]"    # or: openai,dev | ollama,dev | gemini,dev | all,dev

# Setup config
cp .env.example .env                  # fill in API keys

# Run tests (no API keys needed — all SDKs are mocked)
pytest tests/ -v
pytest tests/test_llm_factory.py -v                       # single module
pytest tests/test_llm_providers.py::TestAnthropicProvider -v  # single class

# Lint
ruff check src/ tests/
ruff format src/ tests/
```

---

## Dev Notes

**After removing a git worktree**, run `pip install -e ".[anthropic,dev]"` from
the repo root. The editable install's `.pth` file records the worktree's `src/`
path; once the worktree is deleted, `import coach` breaks until reinstalled.

The `dev` extra does **not** include any LLM provider SDK. Always install a
provider extra together with `dev` (e.g. `.[anthropic,dev]`).
