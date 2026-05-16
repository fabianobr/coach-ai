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
from src.coach.telegram.formatting import markdown_to_html


def load_program():
    """Load the training program from data/program.json."""
    program_path = Path(__file__).parent.parent / "data" / "programs" / "powerbuilding-4d.json"
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
            program_path = Path(__file__).parent.parent / "data" / "programs" / "powerbuilding-4d.json"
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
            program_path = Path(__file__).parent.parent / "data" / "programs" / "powerbuilding-4d.json"
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
            program_path = Path(__file__).parent.parent / "data" / "programs" / "powerbuilding-4d.json"
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
            program_path = Path(__file__).parent.parent / "data" / "programs" / "powerbuilding-4d.json"
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
            program_path = Path(__file__).parent.parent / "data" / "programs" / "powerbuilding-4d.json"
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


class TestMarkdownToHtml:
    """Test the markdown_to_html converter for safety-net LLM response handling."""

    def test_bold_double_asterisk(self):
        """Convert **bold** → <b>bold</b>."""
        result = markdown_to_html("This is **bold** text")
        assert result == "This is <b>bold</b> text"

    def test_bold_double_underscore(self):
        """Convert __bold__ → <b>bold</b>."""
        result = markdown_to_html("This is __bold__ text")
        assert result == "This is <b>bold</b> text"

    def test_italic_single_asterisk(self):
        """Convert *italic* → <i>italic</i>."""
        result = markdown_to_html("This is *italic* text")
        assert result == "This is <i>italic</i> text"

    def test_italic_single_underscore(self):
        """Convert _italic_ → <i>italic</i>."""
        result = markdown_to_html("This is _italic_ text")
        assert result == "This is <i>italic</i> text"

    def test_inline_code_single_backtick(self):
        """Convert `code` → <code>code</code>."""
        result = markdown_to_html("Use the `command` here")
        assert result == "Use the <code>command</code> here"

    def test_code_block_triple_backtick(self):
        """Convert ```code block``` → <pre>code block</pre>."""
        result = markdown_to_html("```\ncode block\n```")
        assert result == "<pre>\ncode block\n</pre>"

    def test_code_block_multiline(self):
        """Code blocks should handle multiple lines correctly."""
        code = """```
line 1
line 2
```"""
        result = markdown_to_html(code)
        assert "<pre>" in result
        assert "line 1" in result
        assert "line 2" in result

    def test_heading_single_hash(self):
        """Convert # Heading → <b>Heading</b>."""
        result = markdown_to_html("# Main Title")
        assert result == "<b>Main Title</b>"

    def test_heading_double_hash(self):
        """Convert ## Heading → <b>Heading</b>."""
        result = markdown_to_html("## Sub Title")
        assert result == "<b>Sub Title</b>"

    def test_heading_triple_hash(self):
        """Convert ### Heading → <b>Heading</b>."""
        result = markdown_to_html("### Sub-sub Title")
        assert result == "<b>Sub-sub Title</b>"

    def test_mixed_markdown_and_html(self):
        """Mixed Markdown and HTML should convert only Markdown parts."""
        result = markdown_to_html("Use <b>HTML</b> or **Markdown** for bold")
        assert "<b>HTML</b>" in result
        assert "<b>Markdown</b>" in result

    def test_already_html_tags_pass_through(self):
        """HTML tags should not be modified."""
        result = markdown_to_html("This is <b>already bold</b>")
        assert result == "This is <b>already bold</b>"

    def test_empty_string(self):
        """Empty string should remain empty."""
        result = markdown_to_html("")
        assert result == ""

    def test_no_markdown(self):
        """Text with no Markdown should pass through unchanged."""
        result = markdown_to_html("Just plain text here")
        assert result == "Just plain text here"

    def test_nested_patterns(self):
        """Nested patterns should be handled correctly."""
        result = markdown_to_html("This **contains *mixed* formatting**")
        assert "<b>" in result
        assert "<i>" in result

    def test_multiple_bold_sections(self):
        """Multiple bold sections should all be converted."""
        result = markdown_to_html("**first** and **second** and **third**")
        assert result == "<b>first</b> and <b>second</b> and <b>third</b>"

    def test_bold_before_italic(self):
        """Bold should be converted before italic to avoid partial matches."""
        result = markdown_to_html("**bold** and *italic*")
        assert result == "<b>bold</b> and <i>italic</i>"
        assert "**" not in result

    def test_code_before_bold(self):
        """Code should be converted before bold to avoid partial matches."""
        result = markdown_to_html("`**not bold**`")
        assert "<code>**not bold**</code>" in result
        assert "<b>" not in result

    def test_llm_response_typical(self):
        """Test a typical LLM response with mixed Markdown."""
        llm_response = """**Language Spotter**: You said "I do 5x5", but say *completed* or *did* instead.

**Coach's Tip**: Here's your `next exercise`:
- **Back Squat**: Keep your chest up
- *Weight*: focus on depth
"""
        result = markdown_to_html(llm_response)
        assert "<b>Language Spotter</b>" in result
        assert "<i>completed</i>" in result
        assert "<code>next exercise</code>" in result
        assert "<b>Back Squat</b>" in result
        assert "<i>Weight</i>" in result
        assert "**" not in result
        assert "*" not in result or "<i>" in result  # single asterisks converted to italic

    def test_preserve_html_entities(self):
        """HTML entities like &amp; should work correctly."""
        result = markdown_to_html("Use **bold** & `code`")
        assert "<b>bold</b>" in result
        assert "<code>code</code>" in result


class TestMarkdownTableConverter:
    """Test the Markdown table-to-<pre> converter for LLM-generated tables."""

    def test_simple_table_wrapped_in_pre(self):
        """Single Markdown table should be wrapped in <pre>.</pre>"""
        table = """| # | Exercise |
|---|----------|
| 1 | Back Squat |"""
        result = markdown_to_html(table)
        assert "<pre>" in result
        assert "</pre>" in result
        # Separator row should be removed
        assert "|---|" not in result
        # Data rows should remain
        assert "| # | Exercise |" in result
        assert "| 1 | Back Squat |" in result

    def test_multi_row_table(self):
        """Multi-row table should strip separators and wrap in <pre>."""
        table = """| # | Status | Exercise |
|---|--------|----------|
| 1 | ✅ DONE | Back Squat |
| 2 | ⏳ PENDING | Leg Press |"""
        result = markdown_to_html(table)
        assert "<pre>" in result
        assert "| # | Status | Exercise |" in result
        assert "| 1 | ✅ DONE | Back Squat |" in result
        assert "| 2 | ⏳ PENDING | Leg Press |" in result
        # Separators removed
        assert "|---|" not in result
        assert "|--------|" not in result

    def test_table_followed_by_text(self):
        """Table block followed by normal text should only wrap the table."""
        text = """| # | Exercise |
|---|----------|
| 1 | Squat |

Now let's continue."""
        result = markdown_to_html(text)
        assert "<pre>" in result
        assert "| # | Exercise |" in result
        assert "Now let's continue." in result
        # The non-table text should not be in <pre>
        assert "<pre>Now" not in result

    def test_text_followed_by_table(self):
        """Normal text followed by table should only wrap the table."""
        text = """Status update:

| # | Exercise |
|---|----------|
| 1 | Squat |"""
        result = markdown_to_html(text)
        assert "Status update:" in result
        assert "<pre>" in result
        assert "| # | Exercise |" in result

    def test_multiple_tables(self):
        """Multiple separate tables should each be wrapped."""
        text = """| # | A |
|---|---|
| 1 | X |

Some text in between.

| # | B |
|---|---|
| 2 | Y |"""
        result = markdown_to_html(text)
        # Count <pre> tags
        pre_count = result.count("<pre>")
        assert pre_count == 2
        # Both tables present
        assert "| # | A |" in result
        assert "| # | B |" in result

    def test_no_table_unchanged(self):
        """Text with no tables should pass through unchanged."""
        text = "No pipes here, just regular text."
        result = markdown_to_html(text)
        assert result == text
        assert "<pre>" not in result

    def test_already_html_pre_unchanged(self):
        """<pre> blocks already in HTML should not be modified."""
        text = "<pre>Already pre-formatted code</pre>"
        result = markdown_to_html(text)
        assert "<pre>Already pre-formatted code</pre>" in result

    def test_session_status_format(self):
        """Test typical Session Status table from LLM response."""
        session_status = """| # | Status | Exercise       | Weight  | Sets×Reps |
|----|--------|----------------|---------|-----------|
| 1  | ✅ DONE | Back Squat     | 110kg   | 5×5       |
| 2  | ⏳ PENDING | Leg Press 45° | 90kg/side | 3×8   |"""
        result = markdown_to_html(session_status)
        assert "<pre>" in result
        assert "✅ DONE" in result
        assert "⏳ PENDING" in result
        # Separators removed
        assert "|----|" not in result
        assert "|--------|" not in result

    def test_table_with_complex_content(self):
        """Table with formatting and special chars should be wrapped correctly."""
        table = """| Exercise | Notes |
|----------|-------|
| **Squat** | `45kg/side` |"""
        result = markdown_to_html(table)
        assert "<pre>" in result
        # The table itself is wrapped, but **bold** inside table converts too
        assert "<b>Squat</b>" in result
        assert "<code>45kg/side</code>" in result

    def test_table_with_line_breaks(self):
        """Table preserves line breaks within the table block."""
        table = """| # | Exercise |
|---|----------|
| 1 | Squat |
| 2 | Bench |"""
        result = markdown_to_html(table)
        assert "<pre>" in result
        # Both rows present with structure intact
        assert "| 1 | Squat |" in result
        assert "| 2 | Bench |" in result
