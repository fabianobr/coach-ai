from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from coach.constants import DAY_LABELS


# ---------------------------------------------------------------------------
# Enums / exceptions / dataclasses
# ---------------------------------------------------------------------------

class PRType(str, Enum):
    NONE = "none"
    VOLUME = "volume"
    WEIGHT = "weight"


class ExerciseStatus(str, Enum):
    DONE = "done"
    SKIPPED = "skipped"
    INCOMPLETE = "incomplete"


class MissingDataError(ValueError):
    def __init__(self, exercise_name: str, field_name: str) -> None:
        super().__init__(f"Missing {field_name} for exercise '{exercise_name}'")


@dataclass
class ExerciseResult:
    name: str
    sets: int
    reps_done: int | None          # None for isometric
    weight_kg: float | None        # None for isometric
    tonnage_kg: float | None       # None for isometric
    tut_seconds: int | None        # Only for isometric: hold_seconds × sets
    status: ExerciseStatus
    pr_type: PRType = PRType.NONE


@dataclass
class SessionLog:
    date: str                      # YYYY-MM-DD
    day_id: str                    # D1, D2, D4, D5
    exercises: list[ExerciseResult] = field(default_factory=list)
    total_tonnage_kg: float = 0.0
    duration_minutes: int = 0


# ---------------------------------------------------------------------------
# Tonnage calculation
# ---------------------------------------------------------------------------

_BARBELL_BAR_KG = 20.0


def compute_tonnage(
    exercise_type: str,
    weight_kg: float | None,
    reps: int,
    sets: int,
    weight_per_side_kg: float | None = None,
    is_isometric: bool = False,
) -> float | None:
    """
    Returns the tonnage for an exercise, or None for isometric exercises.

    Barbell formula: (weight_per_side_kg × 2 + 20kg bar) × reps × sets
    Machine/cable/dumbbell/weighted: weight_kg × reps × sets
    Isometric: None (track as TuT)
    """
    if is_isometric or exercise_type == "isometric":
        return None

    if exercise_type == "barbell":
        if weight_per_side_kg is None:
            return None
        total_weight = weight_per_side_kg * 2 + _BARBELL_BAR_KG
        return total_weight * reps * sets

    if weight_kg is None:
        return None
    return weight_kg * reps * sets


# ---------------------------------------------------------------------------
# Session logger
# ---------------------------------------------------------------------------

class SessionLogger:
    def __init__(
        self,
        logs_dir: Path | None = None,
        templates_dir: Path | None = None,
    ) -> None:
        _root = Path(__file__).parent.parent.parent
        self.logs_dir = logs_dir or (_root / "logs")
        self.templates_dir = templates_dir or (_root / "templates")
        self._results: list[ExerciseResult] = []

    def record(self, exercise_result: ExerciseResult) -> None:
        """Accumulate an exercise result; raises MissingDataError for invalid non-isometric entries."""
        if (
            exercise_result.tut_seconds is None
            and exercise_result.reps_done is not None
            and exercise_result.weight_kg is None
            and exercise_result.status == ExerciseStatus.DONE
        ):
            raise MissingDataError(exercise_result.name, "weight_kg")
        self._results.append(exercise_result)

    def save(self, day_id: str, date: str, duration_minutes: int = 0) -> Path:
        """Write session log to logs/{date}.md. Raises FileExistsError if already exists."""
        if day_id not in DAY_LABELS:
            raise ValueError(f"Invalid day_id: {day_id}. Must be one of {list(DAY_LABELS)}")

        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.logs_dir / f"{date}.md"

        if log_path.exists():
            raise FileExistsError(f"Log already exists: {log_path}")

        total_tonnage = sum(
            r.tonnage_kg for r in self._results if r.tonnage_kg is not None
        )
        day_label = DAY_LABELS[day_id]

        lines: list[str] = [
            f"# Daily Training Log — {day_label} | {date}",
            "",
            "---",
            "",
            "## Session Overview",
            "",
            "| Field | Value |",
            "| :--- | :--- |",
            f"| **Date** | {date} |",
            f"| **Day** | {day_id} — {day_label} |",
            f"| **Total Tonnage** | {total_tonnage:.0f} kg |",
            f"| **Session Duration** | {duration_minutes} min |",
            "",
            "---",
            "",
            f"## Exercise Tracking",
            "",
            f"### {day_id}: {day_label}",
            "",
            "| # | Status | Exercise | Target | Weight (kg) | Sets × Reps | Tonnage (kg) | Notes |",
            "| :---: | :---: | :--- | :--- | :---: | :---: | :---: | :--- |",
        ]

        for i, r in enumerate(self._results, start=1):
            status_icon = _status_icon(r)
            if r.status in (ExerciseStatus.SKIPPED, ExerciseStatus.INCOMPLETE):
                lines.append(f"| {i} | {status_icon} | {r.name} | — | — | — | — | |")
            elif r.tut_seconds is not None:
                hold = r.tut_seconds // r.sets if r.sets else r.tut_seconds
                lines.append(
                    f"| {i} | {status_icon} | {r.name} | — | — "
                    f"| {r.sets}×{hold}s | TuT: {r.tut_seconds}s |"
                )
            else:
                target = (
                    f"{r.sets}×{r.reps_done} @ {r.weight_kg}kg"
                    if r.reps_done and r.weight_kg else "—"
                )
                tonnage_str = f"{r.tonnage_kg:.0f}" if r.tonnage_kg is not None else "—"
                reps_str = f"{r.sets}×{r.reps_done}" if r.reps_done else "—"
                weight_str = str(r.weight_kg) if r.weight_kg is not None else "—"
                lines.append(
                    f"| {i} | {status_icon} | {r.name} | {target} "
                    f"| {weight_str} | {reps_str} | {tonnage_str} | |"
                )

        done_count = sum(1 for r in self._results if r.status == ExerciseStatus.DONE)
        skipped_count = sum(1 for r in self._results if r.status == ExerciseStatus.SKIPPED)
        pr_count = sum(1 for r in self._results if r.pr_type != PRType.NONE)

        lines += [
            "",
            "> **Status legend:** ✅ DONE | ⏳ PENDING | ❌ SKIPPED | 🏆 Volume PR | 💪 Weight PR",
            "",
            "---",
            "",
            "## Session Summary",
            "",
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| Exercises completed | {done_count} |",
            f"| Exercises skipped | {skipped_count} |",
            f"| PRs achieved | {pr_count} |",
            f"| Total tonnage | {total_tonnage:.0f} kg |",
            "",
        ]

        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return log_path

    def detect_prs(
        self,
        exercise_name: str,
        weight_kg: float | None,
        tonnage_kg: float | None,
    ) -> PRType:
        """Compare against prior logs; return WEIGHT if new weight PR, else NONE."""
        prior_paths = self.get_prior_log_paths()
        if not prior_paths:
            return PRType.NONE

        max_weight: float | None = None
        for path in prior_paths:
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for line in content.splitlines():
                if "|" not in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                # Table row: | # | status | name | target | weight | reps | tonnage | notes |
                # After split: ['', '1', 'icon', 'name', 'target', 'weight', 'reps', 'tonnage', 'notes', '']
                if len(parts) >= 6 and parts[3] == exercise_name:
                    weight_cell = parts[5] if len(parts) > 5 else ""
                    try:
                        w = float(weight_cell.replace("kg", "").strip())
                        if max_weight is None or w > max_weight:
                            max_weight = w
                    except ValueError:
                        pass

        if weight_kg is not None and max_weight is not None and weight_kg > max_weight:
            return PRType.WEIGHT

        return PRType.NONE

    def get_prior_log_paths(self) -> list[Path]:
        """Return sorted list of all logs/*.md files."""
        if not self.logs_dir.exists():
            return []
        return sorted(self.logs_dir.glob("*.md"))

    def clear(self) -> None:
        self._results = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status_icon(result: ExerciseResult) -> str:
    if result.pr_type == PRType.WEIGHT:
        return "💪"
    if result.pr_type == PRType.VOLUME:
        return "🏆"
    if result.status == ExerciseStatus.DONE:
        return "✅"
    if result.status == ExerciseStatus.SKIPPED:
        return "❌"
    return "⏳"
