# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**coach-ai** is a dual-role virtual coach that:
1. **Tracks gym workouts** — 4-day Powerbuilding split (D1/D2/D4/D5), tonnage calculation, progressive overload, PR detection
2. **Corrects English** — every interaction starts with a "Language Spotter" block fixing the user's grammar/vocabulary

The full AI behavior is defined in `SYSTEM_PROMPT.md`. The Claude Code skill is in `.claude/skills/coach/SKILL.md`.

## Quick Start

```bash
# Install dependencies for your chosen LLM provider
pip install -e ".[anthropic]"   # or openai, ollama, gemini, all

# Copy and fill in your provider config
cp .env.example .env

# Run tests
pytest tests/ -v
```

## Project Structure

```
coach-ai/
├── CLAUDE.md                      ← this file
├── SYSTEM_PROMPT.md               ← full AI persona & interaction rules
├── README.md                      ← project overview
├── .env.example                   ← LLM provider config template
├── pyproject.toml                 ← dependencies per provider
├── data/
│   └── program.json               ← training program (D1/D2/D4/D5)
├── templates/
│   ├── daily_tracking_table.md    ← per-session workout log template
│   └── evolution_chart.md         ← weekly progress & PR tracker
├── logs/                          ← session logs (YYYY-MM-DD.md, git-ignored)
├── src/coach/
│   └── llm/                       ← LLM abstraction layer
│       ├── base.py                ← LLMProvider ABC, Message, LLMConfig
│       ├── factory.py             ← get_provider(), config_from_env()
│       └── providers/
│           ├── anthropic.py
│           ├── openai.py
│           ├── ollama.py          ← delegates to OpenAI provider at /v1
│           └── gemini.py
├── tests/
│   ├── test_llm_base.py
│   ├── test_llm_factory.py
│   └── test_llm_providers.py
└── .claude/skills/coach/
    └── SKILL.md                   ← Claude Code skill entry point
```

## LLM Abstraction Layer

The core design is provider-agnostic. Switch providers via `.env` — no code changes needed.

### Usage

```python
from coach.llm import get_provider, Message

llm = get_provider()  # reads from .env
response = llm.chat([Message(role="user", content="squat done 5x5")])

# Streaming
for chunk in llm.stream([Message(role="user", content="bench cues?")]):
    print(chunk, end="", flush=True)
```

### Provider Configuration (`.env`)

```bash
LLM_PROVIDER=anthropic          # anthropic | openai | ollama | gemini
LLM_MODEL=claude-haiku-4-5-20251001   # leave blank for provider default
LLM_API_KEY=                    # or use provider-specific key below
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
LLM_BASE_URL=                   # ollama default: http://localhost:11434/v1
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.7
```

### Default Models

| Provider | Default Model |
| :--- | :--- |
| anthropic | claude-haiku-4-5-20251001 |
| openai | gpt-4o-mini |
| ollama | llama3.2 |
| gemini | gemini-2.0-flash |

## Training Program

Defined in `data/program.json`. Four days:

| Day | Focus | Key lifts |
| :--- | :--- | :--- |
| D1 | Lower Strength | Back Squat 5×5, RDL, Leg Press |
| D2 | Upper Strength | Bench Press 5×5, Barbell Row, Incline Bench |
| D4 | Lower Hypertrophy | Hack Squat, Leg Curl, Lunges, Hip Thrust |
| D5 | Upper Hypertrophy | Low Row, Lat Pulldown, Chest Fly, Arms superset |

### Tonnage Formula

- **Barbell:** `(weight_per_side × 2 + 20kg bar) × reps × sets`
- **Machine/cable/dumbbell:** `weight × reps × sets`
- **Isometric (Weighted Plank):** no tonnage — track as TuT (seconds)

## Testing

```bash
# Run all tests (no API keys needed — all providers are mocked)
pytest tests/ -v

# Filter by module
pytest tests/test_llm_factory.py -v
pytest tests/test_llm_providers.py -v
```

Tests use `unittest.mock` and `patch.dict("sys.modules", ...)` to mock provider SDKs. No real API calls are made.

**Important:** When writing new provider tests, always place `isinstance` assertions and `from ... import` statements **inside** the `patch.dict` context — not after it exits. This prevents class identity mismatches due to module cache cleanup.

## Conventions

- All output in **English**
- Missing data → `"N/A"`, never invented
- Isometric exercises tracked by TuT (seconds), not tonnage
- Logs saved to `logs/YYYY-MM-DD.md` (git-ignored)
- Follow Conventional Commits: `feat:`, `fix:`, `chore:`, `test:`

## Next Steps (In Development)

- **Coach core** — CLI entry point (`python -m coach`) with full interaction loop
- **Session logger** — persist workouts to `logs/YYYY-MM-DD.md`
- **REST API** — FastAPI `/chat` endpoint
- **Telegram bot** — handler for workout queries
