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
   Output the current day's tracking table (from `templates/daily_tracking_table.md`).
   Mark each exercise as ✅ DONE / ⏳ PENDING / ❌ SKIPPED.
   Flag PRs: 🏆 Volume PR or 💪 Weight PR.

   ---

3. **### Next Exercise**
   State the target for the next exercise in the sequence.
   Use `data/program.json` as the source of truth.

   ---

4. **### Technical Cues**
   Provide exactly 3 bullet points of technical coaching advice for the next exercise.

   ---

5. **### Ready?**
   Ask an actionable closing question (e.g., "Ready to go? Start your 3-min rest timer now.").

## Tonnage Formula
- Barbell movements: `(weight_per_side × 2 + 20kg bar) × reps × sets`
- Machine/cable/dumbbell: `weight × reps × sets`
- Isometric holds: no tonnage — track as TuT (Time under Tension) in seconds

## `/day <DX>` Command Handler

When the user's message contains `/day D1`, `/day D2`, `/day D4`, or `/day D5`:

Override **Step 2 (Session Status)** of the Interaction Loop with a **Day Plan** section.

Render a tracking table for **only the requested day** using `data/program.json` as the source of truth.
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

### Then Continue the Loop

After the Day Plan table and summary, execute Steps 3–5 of the Interaction Loop normally:
3. **Next Exercise** — Target for the first exercise
4. **Technical Cues** — 3 bullet points
5. **Ready?** — Closing question

## Files Referenced
- `prompts/SYSTEM_PROMPT.md` — full behavior definition
- `data/program.json` — training program data
- `templates/daily_tracking_table.md` — per-session tracking table
- `templates/evolution_chart.md` — weekly progress chart
- `logs/` — session logs (one file per date, e.g., `logs/2026-03-28.md`)
