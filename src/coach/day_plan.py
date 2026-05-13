"""Day Plan table rendering utilities for Telegram bot and other interfaces."""

from typing import Any

from coach.constants import DAY_LABELS

TRAINING_DAYS = ["D1", "D2", "D4", "D5"]


def format_weight(exercise: dict[str, Any]) -> str:
    """Format weight display based on exercise type and available fields."""
    exercise_type = exercise.get("type", "")

    if exercise.get("isometric"):
        return "—"

    # Barbell: use total_weight_kg
    if exercise_type == "barbell" and "total_weight_kg" in exercise:
        return f"{exercise['total_weight_kg']:.0f}kg"

    # Cable/machine: use weight_kg
    if exercise_type in ("cable", "machine", "weighted") and "weight_kg" in exercise:
        return f"{exercise['weight_kg']:.1f}kg"

    # Dumbbell with range: X–Ykg/side
    if exercise_type == "dumbbell":
        if "weight_per_side_kg_min" in exercise and "weight_per_side_kg_max" in exercise:
            min_w = exercise["weight_per_side_kg_min"]
            max_w = exercise["weight_per_side_kg_max"]
            return f"{min_w:.1f}–{max_w:.1f}kg/side"
        elif "weight_per_side_kg" in exercise:
            return f"{exercise['weight_per_side_kg']:.1f}kg/side"

    # Machine with per-side weight
    if exercise_type == "machine" and "weight_per_side_kg" in exercise:
        return f"{exercise['weight_per_side_kg']:.1f}kg/side"

    return "—"


def format_sets_reps(exercise: dict[str, Any]) -> str:
    """Format sets × reps based on exercise data."""
    sets = exercise.get("sets", "?")

    if exercise.get("isometric"):
        hold_seconds = exercise.get("hold_seconds", "?")
        return f"{sets}×{hold_seconds}s"

    # Fixed reps: 5×5, 3×8, etc.
    if "reps" in exercise:
        reps = exercise["reps"]
        return f"{sets}×{reps}"

    # Rep range: 4×10-12, 3×10-12
    if "reps_min" in exercise and "reps_max" in exercise:
        reps_min = exercise["reps_min"]
        reps_max = exercise["reps_max"]
        return f"{sets}×{reps_min}-{reps_max}"

    return "?×?"


def calculate_tonnage(exercise: dict[str, Any]) -> float | str:
    """Calculate tonnage (volume) for an exercise. Returns float or 'TuT: XXXs' for isometric."""
    if exercise.get("isometric"):
        hold_seconds = exercise.get("hold_seconds", 0)
        sets = exercise.get("sets", 0)
        return f"TuT: {int(hold_seconds * sets)}s"

    sets = exercise.get("sets", 0)

    # Fixed reps
    if "reps" in exercise:
        reps = exercise["reps"]
    else:
        # Rep range: use midpoint
        reps_min = exercise.get("reps_min", 0)
        reps_max = exercise.get("reps_max", reps_min)
        reps = (reps_min + reps_max) / 2

    # Determine weight
    weight = 0
    exercise_type = exercise.get("type", "")

    if exercise_type == "barbell" and "total_weight_kg" in exercise:
        weight = exercise["total_weight_kg"]
    elif "weight_kg" in exercise:
        # Cable, machine, weighted exercises
        weight = exercise["weight_kg"]
    elif "weight_per_side_kg_min" in exercise and "weight_per_side_kg_max" in exercise:
        # Per-side dumbbell with range: use midpoint
        min_w = exercise["weight_per_side_kg_min"]
        max_w = exercise["weight_per_side_kg_max"]
        weight = (min_w + max_w) / 2 * 2
    elif "weight_per_side_kg" in exercise:
        # Per-side dumbbells/machines (count both sides)
        weight = exercise["weight_per_side_kg"] * 2

    tonnage = weight * reps * sets
    return tonnage


def format_tonnage(exercise: dict[str, Any]) -> str:
    """Format tonnage as a string with comma separators."""
    tonnage = calculate_tonnage(exercise)

    if isinstance(tonnage, str):  # Isometric TuT
        return tonnage

    return f"{int(tonnage):,}kg"


def render_day_plan_formatted_list(program: dict, day_id: str) -> tuple[str, float]:
    """
    Render a Day Plan as a formatted list with HTML styling (Telegram HTML mode).
    Returns (formatted_html, total_volume_kg).

    Format:
    <b>1. Exercise Name</b>
       Weight: XXkg | Sets×Reps: N×N | Tonnage: XXXXkg

    Optimized for mobile Telegram display with proper visual hierarchy.
    """
    if day_id not in program.get("days", {}):
        return "", 0.0

    day_data = program["days"][day_id]
    exercises = day_data.get("exercises", [])
    total_volume = 0.0
    lines = []

    for ex in exercises:
        order = ex.get("order", "?")
        name = ex.get("name", "Unknown")
        weight = format_weight(ex)
        sets_reps = format_sets_reps(ex)
        tonnage_str = format_tonnage(ex)

        # Calculate total volume (only non-isometric)
        tonnage_val = calculate_tonnage(ex)
        if isinstance(tonnage_val, (int, float)):
            total_volume += tonnage_val

        # Add superset note if applicable
        superset_note = " <i>(SS)</i>" if ex.get("superset_with") else ""

        # Format: bold heading + indented data row
        lines.append(f"<b>{order}. {name}</b>{superset_note}")
        lines.append(f"   <i>Weight:</i> {weight} | <i>Sets×Reps:</i> {sets_reps} | <i>Tonnage:</i> {tonnage_str}")
        lines.append("")  # Blank line between exercises

    # Remove trailing blank lines
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines), total_volume


def render_day_plan_summary(day_id: str, total_volume: float, exercise_count: int) -> str:
    """Render the Day Plan summary line showing total volume and exercise count."""
    return f"<b>Planned Volume:</b> {int(total_volume):,} kg  |  <b>Exercises:</b> {exercise_count}"


def _format_weight_compact(exercise: dict[str, Any]) -> str:
    """Format weight for the compact overview. Isometric shows plate weight instead of '—'."""
    if exercise.get("isometric") and "weight_kg" in exercise:
        return f"{exercise['weight_kg']:.0f}kg"
    return format_weight(exercise)


def render_trainings_overview(program: dict) -> str:
    """
    Render a compact overview of all training days for the /trainings command.

    Format per day:
        <b>D1 — LOWER | STRENGTH</b>
        1. Back Squat — 5×5 @ 110kg
        2. Leg Press 45° — 3×8 @ 180kg
        ...
    """
    sections = []
    for day_id in TRAINING_DAYS:
        label = DAY_LABELS.get(day_id, "")
        exercises = program.get("days", {}).get(day_id, {}).get("exercises", [])
        lines = [f"<b>{day_id} — {label}</b>"]
        for ex in exercises:
            order = ex.get("order", "?")
            name = ex.get("name", "Unknown")
            sets_reps = format_sets_reps(ex)
            weight = _format_weight_compact(ex)
            lines.append(f"{order}. {name} — {sets_reps} @ {weight}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)
