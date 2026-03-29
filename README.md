# coach-ai

Virtual AI coach for gym exercises and English grammar.

## What it does

- **Gym Tracker:** Logs your 4-day Powerbuilding split (D1/D2/D4/D5), calculates tonnage, tracks progressive overload, and flags PRs.
- **English Coach:** Corrects your English in every interaction via a "Language Spotter" block with gym-specific terminology tips.

## Training Split

| Day | Focus |
| :--- | :--- |
| D1 | Lower — Strength |
| D2 | Upper — Strength |
| D4 | Lower — Hypertrophy |
| D5 | Upper — Hypertrophy |

## Project Structure

```
coach-ai/
├── SYSTEM_PROMPT.md              # Full AI behavior definition
├── data/
│   └── program.json              # Training program (exercises, sets, reps, weights)
├── templates/
│   ├── daily_tracking_table.md   # Per-session workout log template
│   └── evolution_chart.md        # Weekly progress & PR tracker
├── .claude/
│   └── skills/
│       └── coach/
│           └── SKILL.md          # Claude Code skill entry point
└── logs/                         # Session logs (one file per date)
```

## Usage

Open this repo in Claude Code. The `coach` skill activates automatically when you report a completed exercise or ask about your training.

Example inputs:
- `squat done, 5x5 at 110kg`
- `what are the cues for bench press?`
- `show me my D2 exercises`

## Disclaimer

This tool does not replace professional coaching or medical advice.
