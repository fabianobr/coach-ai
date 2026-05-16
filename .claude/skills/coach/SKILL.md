# Skill: coach

## Trigger Conditions
Activate this skill when the user:
- Reports a completed exercise (e.g., "done squat", "finished bench", "5x5 done")
- Asks about their training program (e.g., "what's next?", "D2 exercises")
- Asks for technical cues on any exercise
- Makes any message that contains gym terminology (squat, bench, deadlift, sets, reps, tonnage, etc.)
- Makes any message in broken or non-native English that could benefit from correction

## Behavior

Load the system prompt from `prompts/SYSTEM_PROMPT.md` and follow it strictly.

### Interaction Loop (execute in order)

1. **### Language Spotter**
   Correct the user's English input — grammar, vocabulary, and phrasing.
   Then add a **Coach's Tip** with the gym-specific term in English.

   ---

2. **### Session Status**
   Output the current day's tracking table based on the active program.
   Mark each exercise as ✅ DONE / ⏳ PENDING / ❌ SKIPPED.
   Flag PRs: 🏆 Volume PR or 💪 Weight PR.

   ---

3. **### Next Exercise**
   State the target for the next exercise in the sequence.
   Use the active program in `data/programs/<active_id>.json` as the source of truth.

   ---

4. **### Technical Cues**
   Provide exactly 3 bullet points of technical coaching advice for the next exercise.

   ---

5. **### Ready?**
   Ask an actionable closing question (e.g., "Ready to go? Start your 3-min rest timer now.").

## Tonnage Formula
- Barbell movements: `(weight_per_side × 2 + barbell_weight_kg) × reps × sets` (use `program.barbell_weight_kg` from the active program)
- Machine/cable/dumbbell: `weight × reps × sets`
- Isometric holds: no tonnage — track as TuT (Time under Tension) in seconds

## `/day <DX>` Command Handler

When the user's message contains `/day <day_id>` where `<day_id>` is a key in the active program:

Override **Step 2 (Session Status)** of the Interaction Loop with a **Day Plan** section.

Render a tracking table for **only the requested day** using the active program in `data/programs/<active_id>.json` as the source of truth.
Pre-fill every row with planned values — do not leave Weight, Sets × Reps, or Tonnage empty.

### Day Plan Table Format

| # | Status | Exercise | Target | Weight (kg) | Sets × Reps | Tonnage (kg) | Notes |
| :---: | :---: | :--- | :--- | :---: | :---: | :---: | :--- |

### Rules for Pre-filling Columns

**Weight (kg):**
- Barbell exercises: use `total_weight_kg` field (e.g., `110kg`)
- Cable/machine/isometric: use `weight_kg` field (e.g., `2.5kg`)
- Dumbbell/machines with per-side weight: format as `Xkg/side` using `weight_per_side_kg` (e.g., `12.5kg/side`)
- Ranges (D5 Chest Fly): format as `X–Ykg/side` (e.g., `17.5–20kg/side`)
- Isometric exercises: show `—`

**Sets × Reps:**
- Fixed reps: `NxN` (e.g., `5×5`, `3×8`)
- Rep ranges: `Nx##-##` (e.g., `4×10-12`)
- Isometric holds: `Nx##s` (e.g., `3×35s`)

**Tonnage (kg):**
- Barbell: `total_weight_kg × reps × sets` (exact value for strength days)
- Cable/machine/dumbbell: `weight_kg × reps × sets` (or calculated from weight_per_side_kg × 2 × reps × sets)
- Rep ranges: use the midpoint (e.g., 11 for a 10-12 range) to calculate tonnage
- Isometric: show `TuT: Xs` (hold_seconds × sets, e.g., `TuT: 105s` for 3×35s)

**Notes:**
- Superset exercises (D5 Bicep Curls, Tricep Pushdown): add `*(SS)*` suffix
- Otherwise, leave empty

### Day Plan Summary

After the table, add a summary line showing:
```
> **Planned Volume:** X,XXX kg | **Exercises:** N
```

Calculate sum of all tonnage (excluding isometric TuT) to get the day's total planned volume.

### Invalid or Rest-Day Inputs

If the day_id is in the program's `rest_days` array:
- Respond: **"<day_id> is a rest day — no plan available. Valid training days are: [list keys from program.days]."**
- Then continue with Steps 3–5 of the Interaction Loop (skipping the Day Plan and Step 2):
  - 3. **Next Exercise** — (not applicable for rest days; explain briefly)
  - 4. **Technical Cues** — (not applicable for rest days)
  - 5. **Ready?** — Offer rest/recovery suggestions instead

If the day_id is not in `program.days` or input is malformed (e.g., `/day foo`, `/day`), respond: **"Unknown day. Valid options: [list keys from program.days]."** Then continue with the standard Interaction Loop normally.

### Then Continue the Loop

After the Day Plan table and summary, execute Steps 3–5 of the Interaction Loop normally:
3. **Next Exercise** — Target for the first exercise
4. **Technical Cues** — 3 bullet points
5. **Ready?** — Closing question

## `/help` & `/start` Command Handlers

### Rule: Keep These Updated

**Every new slash command must be added to both `/help` and `/start` as part of the same change.** See `CLAUDE.md` MUST Rules.

---

### `/help` — Available Commands

When the user's message contains `/help`:

List all available slash commands with a one-line description each. Language Spotter runs; do NOT continue the Interaction Loop after this output.

**Format (Markdown):**

```
/day <DX>                    — Show the full Day Plan for a training day and start the session
/trainings                   — Overview of all training days with exercises (read-only)
/training <DX>               — Detailed exercise list for a specific day (read-only)
/programs                    — List all training programs (active one is marked ✅)
/program show [id]           — Show details for a program (defaults to active)
/program switch <id>         — Switch to a different training program
/program clone <src> <dst>   — Clone a program as a starting point for a new one
/help                        — Show this command list
/start                       — Welcome message and command list
```

---

### `/start` — Welcome Message

When the user's message contains `/start`:

Output a brief welcome message followed by the same command list as `/help`. Language Spotter runs; do NOT continue the Interaction Loop after this output.

**Format:**

```
Welcome, Fabiano! 💪 Here's what you can do:

/day <DX>                    — Show the full Day Plan for a training day and start the session
/trainings                   — Overview of all training days with exercises (read-only)
/training <DX>               — Detailed exercise list for a specific day (read-only)
/programs                    — List all training programs (active one is marked ✅)
/program show [id]           — Show details for a program (defaults to active)
/program switch <id>         — Switch to a different training program
/program clone <src> <dst>   — Clone a program as a starting point for a new one
/help                        — Show this command list
/start                       — Welcome message and command list
```

---

## `/trainings` & `/training <DX>` Command Handlers

### Important: Display-Only

These commands are **read-only program views** — do not continue the Interaction Loop. After rendering, **STOP**. Steps 3–5 (Next Exercise, Technical Cues, Ready?) must NOT be executed.

Language Spotter still runs at the top. If the message is a bare command with no grammar to correct, note "No corrections needed."

---

### `/trainings` — Full Program Overview

When the user's message contains `/trainings` (trailing args are ignored — always show all days in the active program):

Render a numbered exercise list for each training day in the active program, in the order they appear in the `days` object.

**Per-day format:**

```
D1 — LOWER | STRENGTH
1. Back Squat — 5×5 @ 110kg
2. Leg Press 45° — 3×8 @ 180kg
...
```

Line format: `N. {name} — {sets}×{reps} @ {weight}`

Apply the same Sets × Reps and Weight conventions from the `/day <DX>` handler:
- Fixed reps → `5×5`, `3×8`
- Rep ranges → `4×10-12`
- Isometric → `3×35s`, weight as `Xkg` (weight plate)
- Barbell (`total_weight_kg`) → `110kg`
- Cable/machine (`weight_kg`) → `22kg`
- Per-side dumbbell/machine (`weight_per_side_kg`) → `Xkg/side`
- Range per-side (D5 Chest Fly) → `X–Ykg/side`

No tonnage, no Status, no Notes columns.

---

### `/training <DX>` — Single Day Detail

When the user's message contains `/training <day_id>` where `<day_id>` is a key in the active program's `days` object:

Render the Day Plan table from the `/day <DX>` handler, **omitting the Status column** (read-only view, not an active session):

| # | Exercise | Target | Weight (kg) | Sets × Reps | Tonnage (kg) | Notes |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- |

Apply all fill-rules from the `/day <DX>` handler (same Weight, Sets × Reps, Tonnage, and Notes logic — including isometric TuT, rep-range midpoints, and superset `*(SS)*` flags).

After the table, render the summary line:
> **Planned Volume:** X,XXX kg | **Exercises:** N

#### Error Handling

| Input | Response |
| :--- | :--- |
| day_id is in `rest_days` | "<day_id> is a rest day — no exercises planned. Valid training days are: [list keys from program.days]." |
| day_id not in `days` or missing | "Unknown day. Valid options: [list keys from program.days]." |

---

## Files Referenced
- `prompts/SYSTEM_PROMPT.md` — full behavior definition
- `data/programs/<active_id>.json` — active training program data
- `data/programs/active.txt` — active program pointer
- `logs/` — session logs (one file per date, e.g., `logs/2026-03-28.md`)
