import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── LLM mock responses (realistic HTML, one per exercise) ───────────────────

SQUAT_RESPONSE = (
    "<b>🔤 Language Spotter</b>\n"
    '✅ "Done squat 5x5" → "I completed 5×5 on the Back Squat"\n\n'
    "<b>📊 Session Status — D1</b>\n"
    "<b>1. Back Squat</b> ✅ DONE\n"
    "<i>Weight:</i> 110kg | <i>Sets×Reps:</i> 5×5 | <i>Tonnage:</i> 2,750kg\n\n"
    "<b>2. Leg Press 45°</b> ⏳ PENDING\n"
    "<b>3. RDL / Stiff</b> ⏳ PENDING\n"
    "<b>4. Hip Abduction</b> ⏳ PENDING\n"
    "<b>5. Weighted Plank</b> ⏳ PENDING\n\n"
    "<b>🏋️ Next Exercise: Leg Press 45°</b>\n"
    "Target: 3×8 @ 90kg/side\n\n"
    "Ready? Set your 2-min rest timer now. ⏱"
)

LEG_PRESS_RESPONSE = (
    "<b>🔤 Language Spotter</b>\n"
    '✅ "Leg press done 3x8 at 180kg" → "I completed 3×8 on the Leg Press at 180 kg"\n\n'
    "<b>📊 Session Status — D1</b>\n"
    "<b>1. Back Squat</b> ✅ DONE — 5×5 @ 110kg | 2,750kg\n"
    "<b>2. Leg Press 45°</b> ✅ DONE\n"
    "<i>Weight:</i> 180kg | <i>Sets×Reps:</i> 3×8 | <i>Tonnage:</i> 4,320kg\n\n"
    "<b>3. RDL / Stiff</b> ⏳ PENDING\n"
    "<b>4. Hip Abduction</b> ⏳ PENDING\n"
    "<b>5. Weighted Plank</b> ⏳ PENDING\n\n"
    "<b>🏋️ Next Exercise: RDL / Stiff</b>\n"
    "Target: 3×7 @ 42.5kg/side\n\n"
    "Rest 2 min. You're halfway through the strength block. 💪"
)

RDL_RESPONSE = (
    "<b>🔤 Language Spotter</b>\n"
    "✅ Correct phrasing — well done!\n\n"
    "<b>📊 Session Status — D1</b>\n"
    "<b>1. Back Squat</b> ✅ DONE — 5×5 @ 110kg | 2,750kg\n"
    "<b>2. Leg Press 45°</b> ✅ DONE — 3×8 @ 180kg | 4,320kg\n"
    "<b>3. RDL / Stiff</b> ✅ DONE\n"
    "<i>Weight:</i> 105kg | <i>Sets×Reps:</i> 3×7 | <i>Tonnage:</i> 2,205kg\n\n"
    "<b>4. Hip Abduction</b> ⏳ PENDING\n"
    "<b>5. Weighted Plank</b> ⏳ PENDING\n\n"
    "<b>🏋️ Next Exercise: Hip Abduction</b>\n"
    "Target: 3×15 @ 2.5kg (cable)\n\n"
    "Light weight, but focus on mind-muscle connection. 🎯"
)

HIP_ABD_RESPONSE = (
    "<b>🔤 Language Spotter</b>\n"
    '✅ "Hip abduction 3x15 done" → "I completed 3×15 Hip Abduction on the cable"\n\n'
    "<b>📊 Session Status — D1</b>\n"
    "<b>1. Back Squat</b> ✅ DONE — 5×5 @ 110kg | 2,750kg\n"
    "<b>2. Leg Press 45°</b> ✅ DONE — 3×8 @ 180kg | 4,320kg\n"
    "<b>3. RDL / Stiff</b> ✅ DONE — 3×7 @ 105kg | 2,205kg\n"
    "<b>4. Hip Abduction</b> ✅ DONE\n"
    "<i>Weight:</i> 2.5kg | <i>Sets×Reps:</i> 3×15 | <i>Tonnage:</i> 112.5kg\n\n"
    "<b>5. Weighted Plank</b> ⏳ PENDING\n\n"
    "<b>🏋️ Next Exercise: Weighted Plank</b>\n"
    "Target: 3×35s @ 20kg on back\n\n"
    "Last exercise! Give it everything. 🔥"
)

PLANK_RESPONSE = (
    "<b>🔤 Language Spotter</b>\n"
    '✅ "Plank done 3 sets 35 seconds" → "I completed 3 sets of 35s on the Weighted Plank"\n\n'
    "<b>📊 Session Status — D1</b> ✅ COMPLETE\n"
    "<b>1. Back Squat</b> ✅ DONE — 5×5 @ 110kg | 2,750kg\n"
    "<b>2. Leg Press 45°</b> ✅ DONE — 3×8 @ 180kg | 4,320kg\n"
    "<b>3. RDL / Stiff</b> ✅ DONE — 3×7 @ 105kg | 2,205kg\n"
    "<b>4. Hip Abduction</b> ✅ DONE — 3×15 @ 2.5kg | 112.5kg\n"
    "<b>5. Weighted Plank</b> ✅ DONE\n"
    "<i>3×35s @ 20kg</i> | TuT: 105s\n\n"
    "🎉 All 5 exercises complete! Use /done to save your session."
)

USER_ID = 12345


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_update(user_id: int, text: str):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.chat.send_action = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    return update, MagicMock()


# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def d1_bot():
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()
        bot.system_prompt = "You are a fitness coach. Reply in HTML."
        program_path = Path(__file__).parent.parent / "data" / "programs" / "powerbuilding-4d.json"
        bot.program = json.loads(program_path.read_text())
        bot.provider = MagicMock()
        return bot


# ─── E2E Test ─────────────────────────────────────────────────────────────────

async def test_d1_full_workout_e2e(d1_bot):
    bot = d1_bot

    # ── Step 1: /day D1 ──────────────────────────────────────────────────────
    update, context = make_update(USER_ID, "/day D1")
    context.args = ["D1"]

    await bot.handle_day(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert "D1" in reply
    assert "Back Squat" in reply
    assert "Leg Press" in reply
    assert "RDL" in reply
    assert "Hip Abduction" in reply
    assert "Weighted Plank" in reply
    assert "TuT" in reply
    assert "105s" in reply
    bot.provider.stream.assert_not_called()

    session = bot.store.get_or_create(USER_ID)
    assert session.current_day == "D1"
    assert session.messages == []

    # ── Step 2: Back Squat ───────────────────────────────────────────────────
    bot.provider.stream.return_value = iter([SQUAT_RESPONSE])
    update, context = make_update(USER_ID, "Done squat 5x5 felt solid")

    await bot.handle_message(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert "Back Squat" in reply
    assert "DONE" in reply
    assert "110kg" in reply
    assert "2,750kg" in reply
    assert "Leg Press" in reply  # next exercise cued

    session = bot.store.get_or_create(USER_ID)
    assert len(session.messages) == 2
    assert session.messages[0].role == "user"
    assert session.messages[0].content == "Done squat 5x5 felt solid"
    assert session.messages[1].role == "assistant"

    # ── Step 3: Leg Press 45° ────────────────────────────────────────────────
    bot.provider.stream.return_value = iter([LEG_PRESS_RESPONSE])
    update, context = make_update(USER_ID, "Leg press done 3x8 at 180kg")

    await bot.handle_message(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert "Leg Press 45°" in reply
    assert "DONE" in reply
    assert "180kg" in reply
    assert "4,320kg" in reply
    assert "RDL" in reply

    session = bot.store.get_or_create(USER_ID)
    assert len(session.messages) == 4

    # ── Step 4: RDL / Stiff ──────────────────────────────────────────────────
    bot.provider.stream.return_value = iter([RDL_RESPONSE])
    update, context = make_update(USER_ID, "RDL completed 3x7 with 105kg")

    await bot.handle_message(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert "RDL" in reply
    assert "DONE" in reply
    assert "105kg" in reply
    assert "2,205kg" in reply
    assert "Hip Abduction" in reply

    session = bot.store.get_or_create(USER_ID)
    assert len(session.messages) == 6

    # ── Step 5: Hip Abduction ────────────────────────────────────────────────
    bot.provider.stream.return_value = iter([HIP_ABD_RESPONSE])
    update, context = make_update(USER_ID, "Hip abduction 3x15 done cable 2.5kg")

    await bot.handle_message(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert "Hip Abduction" in reply
    assert "DONE" in reply
    assert "2.5kg" in reply
    assert "112.5kg" in reply
    assert "Weighted Plank" in reply

    session = bot.store.get_or_create(USER_ID)
    assert len(session.messages) == 8

    # ── Step 6: Weighted Plank (isometric) ───────────────────────────────────
    bot.provider.stream.return_value = iter([PLANK_RESPONSE])
    update, context = make_update(USER_ID, "Plank done 3 sets 35 seconds 20kg on back")

    await bot.handle_message(update, context)

    reply = update.message.reply_text.call_args.args[0]
    assert "Weighted Plank" in reply
    assert "DONE" in reply
    assert "TuT" in reply
    assert "105s" in reply

    session = bot.store.get_or_create(USER_ID)
    assert len(session.messages) == 10
    user_msgs = [m for m in session.messages if m.role == "user"]
    asst_msgs = [m for m in session.messages if m.role == "assistant"]
    assert len(user_msgs) == 5
    assert len(asst_msgs) == 5
    assert user_msgs[0].content == "Done squat 5x5 felt solid"
    assert user_msgs[4].content == "Plank done 3 sets 35 seconds 20kg on back"

    # ── Pre-done: populate session.exercises ─────────────────────────────────
    # The bot stores free-text LLM responses in session.messages; structured
    # ExerciseResult objects are set here, simulating a future parser or manual
    # entry flow that feeds the session logger.
    from src.coach.logger import ExerciseResult, ExerciseStatus

    session.exercises = [
        ExerciseResult("Back Squat",     sets=5, reps_done=5,  weight_kg=110.0, tonnage_kg=2750.0, tut_seconds=None, status=ExerciseStatus.DONE),
        ExerciseResult("Leg Press 45°",  sets=3, reps_done=8,  weight_kg=180.0, tonnage_kg=4320.0, tut_seconds=None, status=ExerciseStatus.DONE),
        ExerciseResult("RDL / Stiff",    sets=3, reps_done=7,  weight_kg=105.0, tonnage_kg=2205.0, tut_seconds=None, status=ExerciseStatus.DONE),
        ExerciseResult("Hip Abduction",  sets=3, reps_done=15, weight_kg=2.5,   tonnage_kg=112.5,  tut_seconds=None, status=ExerciseStatus.DONE),
        ExerciseResult("Weighted Plank", sets=3, reps_done=None, weight_kg=None, tonnage_kg=None,  tut_seconds=105,  status=ExerciseStatus.DONE),
    ]

    # ── Step 7: /done ────────────────────────────────────────────────────────
    with patch("src.coach.telegram.bot.SessionLogger") as MockLogger:
        mock_logger = MagicMock()
        MockLogger.return_value = mock_logger
        mock_logger.save = MagicMock(return_value=Path("/tmp/fake.md"))

        update, context = make_update(USER_ID, "/done")
        await bot.handle_done(update, context)

    assert mock_logger.record.call_count == 5
    recorded_names = [c.args[0].name for c in mock_logger.record.call_args_list]
    assert recorded_names == [
        "Back Squat",
        "Leg Press 45°",
        "RDL / Stiff",
        "Hip Abduction",
        "Weighted Plank",
    ]

    assert mock_logger.save.call_count == 1
    assert mock_logger.save.call_args.args[0] == "D1"
    assert mock_logger.save.call_args.args[1] == datetime.now().strftime("%Y-%m-%d")

    reply = update.message.reply_text.call_args.args[0]
    assert "Session complete" in reply
    assert "D1" in reply

    assert USER_ID not in bot.store.sessions
