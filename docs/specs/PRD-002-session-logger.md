# PRD: Session Logger

> **Note:** This spec is superseded by the dynamic program system implemented in feat/dynamic-programs. See `data/programs/` and `src/coach/programs.py` for the current implementation.

## Problem Statement

Workout data entered during a coaching session is ephemeral — it is lost when the conversation ends. Without persistent logs, the system cannot:
- Detect personal records (PRs) by comparing weight or tonnage against prior sessions
- Generate weekly progress summaries
- Track progressive overload over time
- Provide users with historical data for motivation and accountability

The Session Logger solves this by persisting each workout to a structured markdown file (`logs/YYYY-MM-DD.md`), enabling all downstream analytics and PR detection features.

## Goals

- **Parse and accumulate workout data**: Accept completed exercises (name, sets, reps, weight, status) during or after a session.
- **Write structured logs**: Generate `logs/YYYY-MM-DD.md` files using the `templates/daily_tracking_table.md` format.
- **Detect PRs**: Compare current session against prior logs to identify Volume PRs (tonnage) and Weight PRs (raw weight).
- **Handle schema edge cases**: Account for isometric exercises (TuT instead of tonnage), hypertrophy rep ranges, Chest Fly weight ranges, and supersets.
- **Expose PR data**: Return structured PR flags for use by CLI, REST API, and Telegram bot.

## Non-Goals

- Evolution chart generation (PRD consumed by future task)
- Weekly aggregation and trend analysis
- Exporting or importing logs in other formats
- Real-time session sync (logs are written once, post-session)

## User Stories

1. **As a returning gym user**, after completing a workout session, the system automatically saves my workout log.
   - Acceptance: Within 1 minute of session end, `logs/2026-05-01.md` exists with my completed exercises.

2. **As a user hitting a new weight PR**, the system flags it so I can celebrate.
   - Acceptance: If my Bench Press weight exceeds all prior sessions, a `💪 Weight PR` indicator is displayed and logged.

3. **As a user tracking volume**, I want to know when I've accumulated more tonnage in a session than ever before.
   - Acceptance: If my total session tonnage exceeds my previous record, a `🏆 Volume PR` indicator is shown.

4. **As a user with isometric exercises**, my Time under Tension is tracked separately from tonnage.
   - Acceptance: Weighted Plank is logged with `TuT: XXs`, not a tonnage value.

5. **As a user reviewing my logs**, I can open `logs/2026-05-01.md` in a text editor and see a formatted workout table.
   - Acceptance: The file is readable markdown with proper tables, dates, and exercise details.

## Functional Requirements

### Data Models

#### `ExerciseResult` (dataclass)
```python
@dataclass
class ExerciseResult:
    name: str                    # e.g., "Back Squat", "Weighted Plank"
    sets: int                    # e.g., 5
    reps_done: int | None        # e.g., 5 (None for isometric)
    weight_kg: float | None      # e.g., 110.0 (None for isometric)
    tonnage_kg: float | None     # computed; None for isometric
    tut_seconds: int | None      # Time under Tension; only for isometric
    status: str                  # "done", "skipped", "incomplete"
    pr_type: str                 # "none", "volume", "weight"
```

#### `SessionLog` (dataclass)
```python
@dataclass
class SessionLog:
    date: str                    # YYYY-MM-DD format
    day_id: str                  # "D1", "D2", "D4", "D5"
    exercises: list[ExerciseResult]
    total_tonnage_kg: float      # sum of all non-isometric tonnage
    duration_minutes: int        # session duration (optional; default 0)
```

### Tonnage Calculation

All formulas are derived from `SYSTEM_PROMPT.md` and must be identical to those in the skill:

| Exercise Type | Formula | Notes |
|---|---|---|
| **Barbell** (Squat, Bench, Row, RDL, Incline Bench) | `(weight_per_side × 2 + 20) × reps × sets` | 20 kg is the fixed bar weight |
| **Machine/Cable/Dumbbell** | `weight_kg × reps × sets` | Single weight value |
| **Isometric** (Weighted Plank) | `None` (use TuT instead) | Track `hold_seconds × sets` as TuT |

### PR Detection

#### Volume PR
- Compare current session's `total_tonnage_kg` against all prior `logs/*.md` files.
- If current > max(prior), flag as Volume PR.

#### Weight PR (per exercise)
- For each exercise in the current session, compare `weight_kg` against the same exercise in all prior logs.
- If current weight > max(prior weight for that exercise), flag as Weight PR.
- **Note**: Weight PR is exercise-specific (e.g., Bench Press Weight PR does not affect Squat).

#### PR Precedence
- Weight PR takes precedence over Volume PR in display (if both apply to the same exercise, show 💪).
- Session Volume PR is separate; displayed at session summary level.

### Log File Format

Use `templates/daily_tracking_table.md` variables:
```markdown
# {{DAY_LABEL}} — {{DATE}}

| Field | Value |
|---|---|
| Date | {{DATE}} |
| Day | {{DAY}} |
| Total Tonnage (kg) | {{TOTAL_TONNAGE}} |
| Session Duration (min) | {{DURATION}} |

## Exercises

| # | Status | Exercise | Target | Weight (kg) | Sets × Reps | Tonnage (kg) | Notes |
|---|---|---|---|---|---|---|---|
| 1 | ✅ | Back Squat | 5×5 @ 110kg | 110 | 5×5 | 5500 | |
| 2 | ⏳ | Leg Press | 3×8 @ 150kg | — | — | — | |
| 3 | 🏆 | RDL | 3×5 @ 120kg | 120 | 3×5 | 1800 | Volume PR |
| ...| ... | ... | ... | ... | ... | ... | ... |

## Summary

| Metric | Value |
|---|---|
| Exercises completed | 3 |
| Exercises skipped | 0 |
| PRs achieved | 1 |
| Total tonnage | 7300 kg |
```

### Edge Cases

#### Hypertrophy Exercises (`reps_min`/`reps_max`)
- The user reports actual reps completed (not a range).
- Use actual reps in tonnage formula: `weight × actual_reps × sets`.
- Example: "Leg Curl 4×8 at 80kg" (within the 3-10 range) → tonnage = 80 × 8 × 4 = 2560 kg.

#### Chest Fly (`weight_per_side_kg_min`/`weight_per_side_kg_max`)
- `data/program.json` defines a range (e.g., 10-20 kg per side).
- The LLM must ask the user for the actual weight used; the logger receives the concrete value.
- Tonnage: `weight × reps × sets`.

#### Weighted Plank (Isometric)
- `data/program.json` has `isometric: true`, `hold_seconds: 30`, `sets: 3`.
- Tonnage = `None` (isometric exercises don't use tonnage).
- TuT (Time under Tension) = `hold_seconds × sets` (e.g., 30 × 3 = 90 seconds).
- Log entry: `3 | ✅ | Weighted Plank | — | — | 3×30s | TuT: 90s |`

#### Supersets (Bicep Curls / Tricep Pushdown)
- Both exercises have `superset_with` field in `data/program.json` linking them.
- Log as two separate rows but add a note indicating they're a superset.
- Tonnage is computed individually for each.

### API

```python
class SessionLogger:
    def record(self, exercise_result: ExerciseResult) -> None:
        """Accumulate an exercise result in the current session."""
        ...
    
    def save(self, day_id: str, date: str, duration_minutes: int = 0) -> Path:
        """
        Write the accumulated session to logs/YYYY-MM-DD.md.
        Returns the Path to the written file.
        Raises FileExistsError if the log already exists.
        """
        ...
    
    def detect_prs(self, exercise_name: str, weight_kg: float | None, tonnage_kg: float) -> str:
        """
        Compare exercise against all prior logs.
        Returns "none", "volume", or "weight".
        """
        ...
    
    def get_prior_logs(self) -> list[Path]:
        """Return sorted list of all logs/YYYY-MM-DD.md files."""
        ...
    
    def parse_log_file(self, path: Path) -> SessionLog:
        """Parse a logs/YYYY-MM-DD.md file back into a SessionLog object."""
        ...
```

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing weight data | Raise `MissingDataError(exercise_name, field)`; never invent values. The caller (CLI, API) must ask the user. |
| Log directory not found | Create `logs/` automatically on first `save()`. |
| Log file already exists | Raise `FileExistsError`; do not overwrite. |
| Corrupt prior log file | Log a warning, skip that file for PR comparison. Continue with valid logs. |
| Invalid date format | Raise `ValueError`; enforce YYYY-MM-DD. |
| Invalid day_id | Raise `ValueError` if not in ["D1", "D2", "D4", "D5"]. |
| Duplicate exercise names in session | Accumulate them separately (both are logged). |

## Testing Criteria

### Unit Tests (`tests/test_logger.py`)

1. **Tonnage calculations**:
   - Barbell: `(110 × 2 + 20) × 5 × 5 = 5500` ✓
   - Machine: `150 × 8 × 3 = 3600` ✓
   - Isometric: `None` (no tonnage) ✓

2. **PR detection**:
   - Volume PR: Current session tonnage > max(prior sessions) ✓
   - Weight PR: Current exercise weight > max(prior exercise weight) ✓
   - No PR: All metrics match or are lower ✓

3. **Log file format**:
   - File is valid markdown ✓
   - Variables are filled in (`{{DATE}}`, etc.) ✓
   - Table structure is correct ✓

4. **Edge case handling**:
   - Hypertrophy rep range → use actual reps ✓
   - Isometric → TuT, no tonnage ✓
   - Chest Fly range → accept concrete value ✓
   - Superset exercises → log as pair ✓

5. **Error handling**:
   - Missing weight raises `MissingDataError` ✓
   - Missing log directory is created ✓
   - Corrupt prior log is skipped with warning ✓

### Integration Test
1. Create a session log for D1 with known exercises.
2. Write it to disk.
3. Create a second session with higher tonnage.
4. Verify Volume PR is detected.
5. Create a third session with same tonnage but higher individual weights.
6. Verify Weight PRs are detected.

### Manual Verification
```python
from src.coach.logger import SessionLogger, ExerciseResult

logger = SessionLogger()
logger.record(ExerciseResult(
    name="Back Squat",
    sets=5, reps_done=5, weight_kg=110,
    tonnage_kg=5500, tut_seconds=None,
    status="done", pr_type="none"
))
path = logger.save(day_id="D1", date="2026-05-01", duration_minutes=45)
print(f"Log written to {path}")
```

## Success Metrics

**The Session Logger is complete and working when:**
1. A D1 session with 5 exercises is logged to `logs/2026-05-01.md`.
2. Tonnage is calculated correctly for all 5 exercises (barbell, machine, cable, dumbbell, isometric).
3. A Volume PR is detected when session tonnage exceeds prior max.
4. A Weight PR is detected when an exercise weight exceeds the prior max for that exercise.
5. Missing weight data raises `MissingDataError` (not silently filled).
6. Log file is readable markdown with properly formatted tables.
7. All tests in `tests/test_logger.py` pass.

---

## Implementation Notes

- Load `data/program.json` at module level to support tonnage formula selection.
- PR detection requires parsing prior `logs/*.md` files; use regex or a markdown parser to extract exercise data.
- Ensure date handling is robust (YYYY-MM-DD format, no timezone issues).
- The barbell weight (20 kg) must be a constant; store it for reference.
