"""Day Plan table rendering utilities for Telegram bot and other interfaces."""

from typing import Any


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


def render_day_plan_table(program: dict, day_id: str) -> tuple[str, float]:
    """
    Render a Day Plan table for the given day using simple pipe-separated format.
    Returns (table_text, total_volume_kg).

    Uses monospace-friendly formatting: left-aligned, pipe-separated, no fancy Unicode.
    """
    if day_id not in program.get("days", {}):
        return "", 0.0

    day_data = program["days"][day_id]
    exercises = day_data.get("exercises", [])

    # Column widths derived from max data lengths across all exercises
    col_widths = {
        "#": 2,
        "Exercise": 23,
        "Weight": 16,
        "Sets×Reps": 9,
        "Tonnage": 10,
        "Notes": 5,
    }

    def left_pad(text: str, width: int) -> str:
        """Left-align text in cell with fixed width."""
        text = str(text)[:width]
        return text.ljust(width)

    lines = []

    # Header separator line
    header_sep = "─" * (sum(col_widths.values()) + len(col_widths) * 3 + 1)
    lines.append(header_sep)

    # Header row
    headers = ["#", "Exercise", "Weight", "Sets×Reps", "Tonnage", "Notes"]
    header_cells = [left_pad(h, col_widths[h]) for h in headers]
    header_row = "| " + " | ".join(header_cells) + " |"
    lines.append(header_row)

    # Header separator line
    lines.append(header_sep)

    total_volume = 0.0

    # Data rows
    for ex in exercises:
        order = str(ex.get("order", "?"))
        name = ex.get("name", "Unknown")
        weight = format_weight(ex)
        sets_reps = format_sets_reps(ex)
        tonnage_str = format_tonnage(ex)

        # Calculate total volume (only non-isometric)
        tonnage_val = calculate_tonnage(ex)
        if isinstance(tonnage_val, (int, float)):
            total_volume += tonnage_val

        # Notes: superset indicator
        notes = "SS" if ex.get("superset_with") else ""

        # Build cells with proper width
        cells = [
            left_pad(order, col_widths["#"]),
            left_pad(name, col_widths["Exercise"]),
            left_pad(weight, col_widths["Weight"]),
            left_pad(sets_reps, col_widths["Sets×Reps"]),
            left_pad(tonnage_str, col_widths["Tonnage"]),
            left_pad(notes, col_widths["Notes"]),
        ]
        row = "| " + " | ".join(cells) + " |"
        lines.append(row)

    # Bottom separator line
    lines.append(header_sep)

    table = "\n".join(lines)
    return table, total_volume


def render_day_plan_summary(day_id: str, total_volume: float, exercise_count: int) -> str:
    """Render the Day Plan summary line showing total volume and exercise count."""
    return f"> **Planned Volume:** {int(total_volume):,} kg | **Exercises:** {exercise_count}"
