# coach-ai

Virtual AI coach for gym exercises and English grammar.

## What it does

- **Gym Tracker:** Logs your workouts on a dynamic training program (configurable days), calculates tonnage, tracks progressive overload, and flags PRs.
- **English Coach:** Corrects your English in every interaction via a "Language Spotter" block with gym-specific terminology tips.

## Training Programs

Training programs are stored as JSON files in `data/programs/`. The active program is identified by `data/programs/active.txt`. Programs can be switched, cloned, and customized without changing any code.

## Project Structure

```
coach-ai/
├── SYSTEM_PROMPT.md              # Full AI behavior definition
├── data/
│   └── programs/
│       ├── active.txt            # Active program pointer
│       └── <program_id>.json     # Training program files (exercises, sets, reps, weights)
├── .claude/
│   └── skills/
│       └── coach/
│           └── SKILL.md          # Claude Code skill entry point
└── logs/                         # Session logs (one file per date)
```

## Usage

Open this repo in Claude Code. The `coach` skill activates automatically when you report a completed exercise or ask about your training.

Slash commands:
- `/day <DX>` — Show the full Day Plan for a training day and start the session
- `/trainings` — Overview of all training days with exercises (read-only)
- `/training <DX>` — Detailed exercise list for a specific day (read-only)
- `/programs` — List all training programs (active one is marked ✅)
- `/program show [id]` — Show details for a program (defaults to active)
- `/program switch <id>` — Switch to a different training program
- `/program clone <src> <dst>` — Clone a program as a starting point for a new one

Example inputs:
- `squat done, 5x5 at 110kg`
- `what are the cues for bench press?`
- `show me my D2 exercises`

## Disclaimer

This tool does not replace professional coaching or medical advice.
