import pytest
from pathlib import Path

from src.coach.logger import (
    ExerciseResult,
    ExerciseStatus,
    MissingDataError,
    PRType,
    SessionLog,
    SessionLogger,
    compute_tonnage,
)


# ---------------------------------------------------------------------------
# compute_tonnage
# ---------------------------------------------------------------------------

def test_tonnage_barbell():
    # (110 * 2 + 20) * 5 * 5 = 240 * 25 = 6000
    result = compute_tonnage("barbell", None, reps=5, sets=5, weight_per_side_kg=110)
    assert result == 6000.0


def test_tonnage_machine():
    # 150 * 8 * 3 = 3600
    result = compute_tonnage("machine", weight_kg=150, reps=8, sets=3)
    assert result == 3600.0


def test_tonnage_cable():
    result = compute_tonnage("cable", weight_kg=22, reps=15, sets=3)
    assert result == 990.0


def test_tonnage_isometric_returns_none():
    result = compute_tonnage("isometric", None, reps=1, sets=3, is_isometric=True)
    assert result is None


def test_tonnage_barbell_with_is_isometric_flag():
    result = compute_tonnage("barbell", None, reps=5, sets=5, weight_per_side_kg=110, is_isometric=True)
    assert result is None


# ---------------------------------------------------------------------------
# SessionLogger.record()
# ---------------------------------------------------------------------------

def make_done_result(name="Back Squat", weight_kg=110.0, sets=5, reps=5):
    return ExerciseResult(
        name=name,
        sets=sets,
        reps_done=reps,
        weight_kg=weight_kg,
        tonnage_kg=compute_tonnage("barbell", None, reps=reps, sets=sets, weight_per_side_kg=weight_kg / 2 - 10),
        tut_seconds=None,
        status=ExerciseStatus.DONE,
    )


def test_record_accumulates(tmp_path):
    logger = SessionLogger(logs_dir=tmp_path)
    r1 = make_done_result("Bench Press", weight_kg=80)
    r2 = make_done_result("Barbell Row", weight_kg=70)
    logger.record(r1)
    logger.record(r2)
    assert len(logger._results) == 2


def test_record_missing_weight_raises(tmp_path):
    logger = SessionLogger(logs_dir=tmp_path)
    bad_result = ExerciseResult(
        name="Bench Press",
        sets=5,
        reps_done=5,
        weight_kg=None,        # Missing!
        tonnage_kg=None,
        tut_seconds=None,
        status=ExerciseStatus.DONE,
    )
    with pytest.raises(MissingDataError):
        logger.record(bad_result)


# ---------------------------------------------------------------------------
# SessionLogger.save()
# ---------------------------------------------------------------------------

def test_save_creates_log_file(tmp_path):
    logger = SessionLogger(logs_dir=tmp_path)
    result = ExerciseResult(
        name="Back Squat", sets=5, reps_done=5, weight_kg=110.0,
        tonnage_kg=6000.0, tut_seconds=None, status=ExerciseStatus.DONE,
    )
    logger.record(result)
    path = logger.save(day_id="D1", date="2026-05-02", duration_minutes=45)
    assert path.exists()
    content = path.read_text()
    assert "D1" in content
    assert "Back Squat" in content
    assert "6000" in content


def test_save_raises_if_file_exists(tmp_path):
    logger = SessionLogger(logs_dir=tmp_path)
    (tmp_path / "2026-05-02.md").write_text("existing")
    with pytest.raises(FileExistsError):
        logger.save(day_id="D1", date="2026-05-02")


def test_save_creates_logs_dir_if_missing(tmp_path):
    new_dir = tmp_path / "new_logs"
    logger = SessionLogger(logs_dir=new_dir)
    logger.save(day_id="D1", date="2026-05-02")
    assert new_dir.exists()


# ---------------------------------------------------------------------------
# SessionLogger.detect_prs()
# ---------------------------------------------------------------------------

def test_detect_prs_no_prior_logs(tmp_path):
    logger = SessionLogger(logs_dir=tmp_path)
    result = logger.detect_prs("Back Squat", weight_kg=110.0, tonnage_kg=6000.0)
    assert result == PRType.NONE


def test_detect_prs_weight_pr(tmp_path):
    # Create a prior log with lower weight
    logger = SessionLogger(logs_dir=tmp_path)
    prior = ExerciseResult(
        name="Back Squat", sets=5, reps_done=5, weight_kg=100.0,
        tonnage_kg=5500.0, tut_seconds=None, status=ExerciseStatus.DONE,
    )
    logger.record(prior)
    logger.save(day_id="D1", date="2026-04-25")

    # New session with higher weight
    logger2 = SessionLogger(logs_dir=tmp_path)
    result = logger2.detect_prs("Back Squat", weight_kg=110.0, tonnage_kg=6000.0)
    assert result == PRType.WEIGHT


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

def test_clear_resets_results(tmp_path):
    logger = SessionLogger(logs_dir=tmp_path)
    logger.record(make_done_result())
    logger.clear()
    assert logger._results == []
