# coach-ai

Virtual AI coach for gym workouts and English grammar correction.

## What it does

- **Gym tracker** — logs workouts on a dynamic training program (configurable
  days), calculates tonnage, detects personal records, and suggests progressive
  overload.
- **English coach** — every interaction begins with a "Language Spotter" block
  that corrects grammar and vocabulary, making English learning organic to the
  coaching experience.

---

## For end users: running the service

### Requirements

- Python ≥ 3.12
- An API key for your chosen LLM provider (or Ollama running locally)

### Installation

```bash
git clone <repo-url>
cd coach-ai
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install a provider extra + dev tools (pick one):
pip install -e ".[anthropic,dev]"   # Anthropic Claude
pip install -e ".[openai,dev]"      # OpenAI
pip install -e ".[ollama,dev]"      # Local Ollama (uses OpenAI-compatible API)
pip install -e ".[gemini,dev]"      # Google Gemini
pip install -e ".[all,dev]"         # All providers

# Configure
cp .env.example .env               # edit .env and fill in your API key
```

### Choosing a runtime

coach-ai runs in four independent modes — pick what fits your use case:

#### Claude Code skill (recommended for Claude users)

Open this repository in [Claude Code](https://claude.ai/code). The `coach` skill
activates automatically when you report an exercise or ask about your training.
No Python setup required.

#### CLI (interactive terminal)

```bash
python -m coach
```

#### REST API

```bash
pip install -e ".[anthropic,rest]"   # rest extra adds FastAPI + uvicorn
python -m coach.api                  # listens on http://127.0.0.1:8000
```

See [`docs/API_GUIDE.md`](docs/API_GUIDE.md) for endpoint reference and examples.

#### Telegram bot

```bash
pip install -e ".[anthropic,telegram]"
# Add TELEGRAM_BOT_TOKEN to .env (get it from @BotFather on Telegram)
python -m coach.telegram
# or use the verified launch script:
python scripts/start_telegram_bot.py
```

See [`docs/TELEGRAM_BOT_SETUP.md`](docs/TELEGRAM_BOT_SETUP.md) for the full
setup guide, including how to get a bot token and how to test the bot.

### Training programs

Programs are JSON files in `data/programs/`. The active program is identified by
the ID in `data/programs/active.txt`. Switch, clone, and customise programs
without touching code:

| Command | Action |
| :-- | :-- |
| `/programs` | List all programs (active one marked ✅) |
| `/program show [id]` | View a program |
| `/program switch <id>` | Activate a different program |
| `/program clone <src> <dst>` | Copy a program as a starting point |

### Example interactions

```
squat done, 5x5 at 110kg
what are the cues for bench press?
/day D1
/programs
```

---

## For contributors: developing coach-ai

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, test, lint, commit
conventions, and PR workflow.

Architecture deep-dive: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## For AI tool users: Cline, Continue, and local LLMs

All project rules, architecture, conventions, and patterns are documented in
[`AGENTS.md`](AGENTS.md). Read it before exploring or modifying code.

Quick setup with a local LLM (e.g. Qwen via Ollama):

```bash
ollama pull qwen2.5:7b
# In .env:
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434/v1
```

---

## Project structure

```
coach-ai/
├── AGENTS.md                     # Project rules for all AI coding assistants
├── CONTRIBUTING.md               # Contributor guide
├── prompts/
│   └── SYSTEM_PROMPT.md          # AI behavior definition (all runtimes)
├── data/programs/
│   ├── active.txt                # Active program ID
│   └── <program_id>.json         # Training program definitions
├── src/coach/
│   ├── llm/                      # Provider-agnostic LLM abstraction layer
│   ├── api/                      # FastAPI REST service
│   ├── telegram/                 # Telegram bot
│   └── cli.py                    # Interactive CLI
├── .claude/skills/coach/
│   └── SKILL.md                  # Claude Code skill entry point
├── tests/                        # pytest test suite (no API keys needed)
└── docs/
    ├── ARCHITECTURE.md
    ├── TELEGRAM_BOT_SETUP.md
    └── API_GUIDE.md
```

---

## Disclaimer

This tool does not replace professional coaching or medical advice.

## License

[MIT](LICENSE) — Copyright (c) 2026 Fabiano de Freitas
