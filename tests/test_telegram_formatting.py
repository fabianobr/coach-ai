"""
Detailed tests to verify Telegram message formatting output.
Tests the actual message content sent to users, including HTML formatting,
code blocks, and table alignment.
"""
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.constants import ParseMode

from src.coach.day_plan import render_day_plan_summary, render_day_plan_formatted_list


def load_program():
    """Load the training program from data/program.json."""
    program_path = Path(__file__).parent.parent / "data" / "program.json"
    with open(program_path) as f:
        return json.load(f)


class TestDayPlanSummaryFormatting:
    """Test the day plan summary line uses correct HTML formatting."""

    def test_summary_uses_html_bold_tags(self):
        """Summary line should use <b> tags, not Markdown ** syntax."""
        result = render_day_plan_summary("D1", 9387.5, 5)

        # Should contain HTML bold tags
        assert "<b>Planned Volume:</b>" in result
        assert "<b>Exercises:</b>" in result

        # Should NOT contain Markdown blockquote syntax (leading "> ")
        assert not result.startswith("> ")
        # Should NOT contain Markdown double-asterisk bold
        assert "**" not in result

    def test_summary_format_exact(self):
        """Summary line should have exact HTML formatting."""
        result = render_day_plan_summary("D1", 5000.0, 5)
        expected = "<b>Planned Volume:</b> 5,000 kg  |  <b>Exercises:</b> 5"
        assert result == expected

    def test_summary_with_large_volume(self):
        """Summary should format large numbers with commas."""
        result = render_day_plan_summary("D1", 12345.67, 6)
        assert "12,345 kg" in result
        assert "<b>Exercises:</b> 6" in result


class TestDayPlanFormattedListFormatting:
    """Test that day plan formatted list renders correctly with HTML."""

    def test_formatted_list_has_bold_exercise_names(self):
        """Formatted list should have bold exercise names."""
        program = load_program()
        formatted_list, _ = render_day_plan_formatted_list(program, "D1")

        # Should contain bold tags around exercise names
        assert "<b>" in formatted_list
        assert "</b>" in formatted_list
        assert "Back Squat" in formatted_list

    def test_formatted_list_has_italic_labels(self):
        """Formatted list should use italic for field labels."""
        program = load_program()
        formatted_list, _ = render_day_plan_formatted_list(program, "D1")

        # Should contain italic tags for labels
        assert "<i>Weight:</i>" in formatted_list
        assert "<i>Sets×Reps:</i>" in formatted_list
        assert "<i>Tonnage:</i>" in formatted_list

    def test_formatted_list_contains_all_exercises(self):
        """Formatted list should include all exercises for the day."""
        program = load_program()
        formatted_list, _ = render_day_plan_formatted_list(program, "D1")

        # D1 exercises from program.json
        assert "Back Squat" in formatted_list
        assert "Leg Press" in formatted_list
        assert "RDL" in formatted_list
        assert "Hip Abduction" in formatted_list
        assert "Weighted Plank" in formatted_list

    def test_formatted_list_shows_correct_weights(self):
        """Formatted list should display weights correctly based on type."""
        program = load_program()
        formatted_list, _ = render_day_plan_formatted_list(program, "D1")

        # Back Squat is barbell with total_weight_kg
        assert "110kg" in formatted_list

        # Leg Press is per-side
        assert "90.0kg/side" in formatted_list

        # Weighted Plank is isometric (shows —)
        assert "—" in formatted_list

    def test_formatted_list_shows_tonnage(self):
        """Formatted list should calculate and display tonnage for each exercise."""
        program = load_program()
        formatted_list, total = render_day_plan_formatted_list(program, "D1")

        # Back Squat: 110kg × 5 × 5 = 2,750kg
        assert "2,750kg" in formatted_list

        # Weighted Plank shows TuT instead of tonnage
        assert "TuT:" in formatted_list and "105" in formatted_list

        # Total volume should match
        assert total == pytest.approx(9387.5, abs=0.1)

    def test_formatted_list_shows_superset_indicator(self):
        """Formatted list should mark superset exercises with (SS)."""
        program = load_program()
        formatted_list, _ = render_day_plan_formatted_list(program, "D5")

        # D5 has superset exercises (Bicep Curls and Tricep Pushdown)
        # Check for superset indicator
        assert "(SS)" in formatted_list

    def test_formatted_list_mobile_friendly(self):
        """Formatted list should be mobile-friendly with reasonable line lengths."""
        program = load_program()
        formatted_list, _ = render_day_plan_formatted_list(program, "D1")

        lines = formatted_list.split("\n")
        # Most lines should be under 100 characters (reasonable for mobile)
        # Note: HTML tags are included in length, so actual display is shorter
        for line in lines:
            assert len(line) < 150, f"Line too long for mobile: {line}"


class TestHandleDayMessageFormatting:
    """Test the full /day command message formatting."""

    @pytest.mark.asyncio
    async def test_day_message_has_html_bold_header(self):
        """The /day message header should use HTML bold formatting."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            from src.coach.telegram.bot import CoachBot

            bot = CoachBot()
            bot.system_prompt = "coach"
            program_path = Path(__file__).parent.parent / "data" / "program.json"
            bot.program = json.loads(program_path.read_text())

            update = MagicMock()
            update.effective_user.id = 999
            update.message.reply_text = AsyncMock()

            context = MagicMock()
            context.args = ["D1"]

            await bot.handle_day(update, context)

            # Get the message that was sent
            call_args = update.message.reply_text.call_args
            message_text = call_args.args[0] if call_args.args else None

            # Should have HTML bold tags
            assert "<b>D1</b>" in message_text
            assert "<b>LOWER | STRENGTH</b>" in message_text

            # Should NOT have Markdown syntax
            assert "*D1*" not in message_text
            assert "**" not in message_text

    @pytest.mark.asyncio
    async def test_day_message_has_formatted_list(self):
        """The /day message should include formatted list with HTML styling."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            from src.coach.telegram.bot import CoachBot

            bot = CoachBot()
            bot.system_prompt = "coach"
            program_path = Path(__file__).parent.parent / "data" / "program.json"
            bot.program = json.loads(program_path.read_text())

            update = MagicMock()
            update.effective_user.id = 999
            update.message.reply_text = AsyncMock()

            context = MagicMock()
            context.args = ["D1"]

            await bot.handle_day(update, context)

            # Get the message that was sent
            call_args = update.message.reply_text.call_args
            message_text = call_args.args[0] if call_args.args else None

            # Should have HTML formatted list (bold exercise names, italic labels)
            assert "<b>" in message_text and "Back Squat" in message_text
            assert "<i>Weight:</i>" in message_text
            assert "<i>Sets×Reps:</i>" in message_text

            # Should NOT have code block backticks
            assert "```" not in message_text

    @pytest.mark.asyncio
    async def test_day_message_has_summary_line(self):
        """The /day message should include formatted summary line."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            from src.coach.telegram.bot import CoachBot

            bot = CoachBot()
            bot.system_prompt = "coach"
            program_path = Path(__file__).parent.parent / "data" / "program.json"
            bot.program = json.loads(program_path.read_text())

            update = MagicMock()
            update.effective_user.id = 999
            update.message.reply_text = AsyncMock()

            context = MagicMock()
            context.args = ["D1"]

            await bot.handle_day(update, context)

            # Get the message that was sent
            call_args = update.message.reply_text.call_args
            message_text = call_args.args[0] if call_args.args else None

            # Should have HTML bold summary
            assert "<b>Planned Volume:</b>" in message_text
            assert "<b>Exercises:</b>" in message_text

            # Should NOT have Markdown blockquote syntax
            assert "> **" not in message_text


class TestHandleStatusMessageFormatting:
    """Test the /status command message formatting."""

    @pytest.mark.asyncio
    async def test_status_message_has_html_bold_header(self):
        """The /status message header should use HTML bold formatting."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            from src.coach.telegram.bot import CoachBot

            bot = CoachBot()
            bot.system_prompt = "coach"
            program_path = Path(__file__).parent.parent / "data" / "program.json"
            bot.program = json.loads(program_path.read_text())

            update = MagicMock()
            update.effective_user.id = 999
            update.message.reply_text = AsyncMock()

            context = MagicMock()

            session = bot.store.get_or_create(999)
            session.current_day = "D2"

            await bot.handle_status(update, context)

            # Get the message that was sent
            call_args = update.message.reply_text.call_args
            message_text = call_args.args[0] if call_args.args else None

            # Should have HTML bold tags wrapping the entire day label
            assert "<b>D2: UPPER | STRENGTH</b>" in message_text

            # Should NOT have Markdown bold syntax
            assert "*D2:" not in message_text


class TestMessageParseMode:
    """Test that messages use correct parse_mode for formatting."""

    @pytest.mark.asyncio
    async def test_handle_day_uses_html_parse_mode(self):
        """handle_day should send message with parse_mode=ParseMode.HTML."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            from src.coach.telegram.bot import CoachBot

            bot = CoachBot()
            bot.system_prompt = "coach"
            program_path = Path(__file__).parent.parent / "data" / "program.json"
            bot.program = json.loads(program_path.read_text())

            update = MagicMock()
            update.effective_user.id = 999
            update.message.reply_text = AsyncMock()

            context = MagicMock()
            context.args = ["D1"]

            await bot.handle_day(update, context)

            # Check that reply_text was called with parse_mode=ParseMode.HTML
            call_args = update.message.reply_text.call_args
            assert call_args.kwargs.get("parse_mode") == ParseMode.HTML or \
                   call_args.kwargs.get("parse_mode") == "HTML"

    @pytest.mark.asyncio
    async def test_handle_start_uses_html_parse_mode(self):
        """handle_start should send message with parse_mode=ParseMode.HTML."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            from src.coach.telegram.bot import CoachBot

            bot = CoachBot()

            update = MagicMock()
            update.effective_user.id = 999
            update.message.reply_text = AsyncMock()

            context = MagicMock()

            await bot.handle_start(update, context)

            # Check that reply_text was called with parse_mode
            call_args = update.message.reply_text.call_args
            assert call_args.kwargs.get("parse_mode") == ParseMode.HTML or \
                   call_args.kwargs.get("parse_mode") == "HTML"

    @pytest.mark.asyncio
    async def test_handle_done_uses_html_parse_mode(self):
        """handle_done should send messages with parse_mode=ParseMode.HTML."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
            from src.coach.telegram.bot import CoachBot

            bot = CoachBot()
            bot.system_prompt = "coach"
            bot.program = {"days": {"D1": {"exercises": []}}}

            update = MagicMock()
            update.effective_user.id = 999
            update.message.reply_text = AsyncMock()

            context = MagicMock()

            session = bot.store.get_or_create(999)
            session.current_day = "D1"

            with patch("src.coach.telegram.bot.SessionLogger") as mock_logger_class:
                mock_logger = MagicMock()
                mock_logger_class.return_value = mock_logger
                mock_logger.save = MagicMock()

                await bot.handle_done(update, context)

            # Check that reply_text was called with parse_mode
            call_args = update.message.reply_text.call_args
            assert call_args.kwargs.get("parse_mode") == ParseMode.HTML or \
                   call_args.kwargs.get("parse_mode") == "HTML"
