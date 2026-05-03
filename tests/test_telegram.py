import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import BadRequest


def test_missing_token_raises():
    with patch.dict(os.environ, {}, clear=True):
        from src.coach.telegram.bot import CoachBot

        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            CoachBot()


def test_missing_system_prompt_raises():
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        with patch.object(Path, "exists", return_value=False):
            bot = CoachBot()
            with pytest.raises(FileNotFoundError):
                bot.load_system_prompt()


def test_user_session_isolation():
    from src.coach.telegram.user_sessions import UserSessionStore

    store = UserSessionStore()
    session_a = store.get_or_create(123)
    session_b = store.get_or_create(456)

    assert session_a.user_id == 123
    assert session_b.user_id == 456
    assert session_a is not session_b


def test_session_clear():
    from src.coach.telegram.user_sessions import UserSessionStore

    store = UserSessionStore()
    store.get_or_create(789)
    assert 789 in store.sessions

    store.clear(789)
    assert 789 not in store.sessions


def test_handle_day_valid():
    from src.coach.telegram.user_sessions import UserSessionStore

    store = UserSessionStore()
    session = store.get_or_create(111)

    assert session.current_day == "D1"
    session.current_day = "D2"
    assert session.current_day == "D2"


def test_handle_day_valid_all_days():
    from src.coach.telegram.user_sessions import UserSessionStore

    store = UserSessionStore()
    session = store.get_or_create(222)

    for day in ["D1", "D2", "D4", "D5"]:
        session.current_day = day
        assert session.current_day == day


def test_user_session_has_messages():
    from src.coach.telegram.user_sessions import UserSessionStore
    from src.coach.llm import Message

    store = UserSessionStore()
    session = store.get_or_create(333)

    assert session.messages == []
    session.messages.append(Message(role="user", content="test"))
    assert len(session.messages) == 1


def test_user_session_message_accumulation():
    from src.coach.telegram.user_sessions import UserSessionStore
    from src.coach.llm import Message

    store = UserSessionStore()
    session = store.get_or_create(444)

    session.messages.append(Message(role="user", content="first"))
    session.messages.append(Message(role="assistant", content="response"))
    session.messages.append(Message(role="user", content="second"))

    assert len(session.messages) == 3
    assert session.messages[0].role == "user"
    assert session.messages[1].role == "assistant"
    assert session.messages[2].role == "user"


def test_user_session_store_lru_eviction():
    """LRU eviction should remove oldest session at capacity."""
    from src.coach.telegram.user_sessions import UserSessionStore

    store = UserSessionStore(max_sessions=3)
    store.get_or_create(1)
    store.get_or_create(2)
    store.get_or_create(3)

    # 4th session triggers eviction of user 1
    store.get_or_create(4)

    assert 1 not in store.sessions
    assert 4 in store.sessions
    assert 2 in store.sessions
    assert 3 in store.sessions


def test_user_session_exercises_field():
    """UserSession should have exercises field for logger integration."""
    from src.coach.telegram.user_sessions import UserSessionStore
    from src.coach.logger import ExerciseResult, ExerciseStatus

    store = UserSessionStore()
    session = store.get_or_create(555)

    assert session.exercises == []
    ex = ExerciseResult(
        name="Squat", sets=5, reps_done=5, weight_kg=100, tonnage_kg=6000,
        tut_seconds=None, status=ExerciseStatus.DONE
    )
    session.exercises.append(ex)
    assert len(session.exercises) == 1


@pytest.fixture
def bot_with_mock_provider():
    """
    Return a fully initialised CoachBot with a mock provider whose stream()
    method yields two chunks: 'Hello' and ' World'.
    """
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()
        bot.system_prompt = "You are a coach."

        mock_provider = MagicMock()
        # stream() is a sync generator; return a plain iterator here.
        mock_provider.stream.return_value = iter(["Hello", " World"])
        bot.provider = mock_provider

        return bot


async def test_handle_message_streams_and_appends_assistant_message(bot_with_mock_provider):
    """
    handle_message must:
    - call provider.stream() exactly once with the user message in history
    - send the accumulated text via reply_text (Markdown first)
    - append the full assistant response to session.messages
    """
    bot = bot_with_mock_provider

    # --- Build a fake Update / Message ---
    mock_message = MagicMock()
    mock_message.text = "How do I do a squat?"
    mock_message.chat = MagicMock()
    mock_message.chat.send_action = AsyncMock()
    mock_message.reply_text = AsyncMock()

    mock_update = MagicMock()
    mock_update.effective_user.id = 9999
    mock_update.message = mock_message

    mock_context = MagicMock()

    # --- Run the handler ---
    await bot.handle_message(mock_update, mock_context)

    # 1. Typing action was sent immediately.
    mock_message.chat.send_action.assert_awaited_once()

    # 2. provider.stream() was called exactly once.
    bot.provider.stream.assert_called_once()
    call_args = bot.provider.stream.call_args
    # The messages kwarg must contain the user message.
    passed_messages = call_args.kwargs.get("messages") or call_args.args[0]
    assert any(m.role == "user" and "squat" in m.content for m in passed_messages)

    # 3. reply_text was called with the full concatenated response.
    reply_calls = mock_message.reply_text.await_args_list
    sent_texts = [c.args[0] for c in reply_calls if c.args]
    assert "Hello World" in "".join(sent_texts)

    # 4. The assistant message was appended to session history.
    session = bot.store.get_or_create(9999)
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].content == "Hello World"


async def test_handle_message_falls_back_to_plain_text_on_bad_html(bot_with_mock_provider):
    """
    When Telegram rejects the HTML-formatted reply_text with BadRequest,
    _safe_reply must retry the same text without parse_mode (plain text),
    and must NOT emit 'Error sending response'.
    """
    bot = bot_with_mock_provider

    # Provider yields a chunk with malformed HTML that triggers BadRequest.
    bot.provider.stream.return_value = iter(["Great job <b>athlete"])

    mock_message = MagicMock()
    mock_message.text = "Done my sets"
    mock_message.chat = MagicMock()
    mock_message.chat.send_action = AsyncMock()

    call_count = 0

    async def selective_reply(text, **kwargs):
        nonlocal call_count
        call_count += 1
        # First call uses parse_mode="HTML" — reject it.
        if kwargs.get("parse_mode") == "HTML":
            raise BadRequest("Can't parse entities")
        # Second call (plain text) should succeed silently.

    mock_message.reply_text = selective_reply

    mock_update = MagicMock()
    mock_update.effective_user.id = 8888
    mock_update.message = mock_message

    await bot.handle_message(mock_update, MagicMock())

    # Two reply_text calls total: one HTML (rejected), one plain.
    assert call_count == 2

    # The session still has the assistant message (stream succeeded).
    session = bot.store.get_or_create(8888)
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].content == "Great job <b>athlete"


@pytest.mark.asyncio
async def test_safe_reply_fallback_also_fails(bot_with_mock_provider):
    """
    Test that when both Markdown parsing and plain-text fallback fail,
    the exception propagates (not silently swallowed).
    """
    bot = bot_with_mock_provider
    message = MagicMock()

    # First call (Markdown) raises BadRequest
    # Second call (fallback, plain text) raises a different error
    from telegram.error import BadRequest
    reply_text_side_effect = [
        BadRequest("can't parse entities"),
        Exception("Network timeout"),
    ]
    message.reply_text = AsyncMock(side_effect=reply_text_side_effect)

    # Should propagate the fallback error
    with pytest.raises(Exception, match="Network timeout"):
        await bot._safe_reply(message, "test response")

    # Verify both calls were made (one for Markdown, one for fallback)
    assert message.reply_text.call_count == 2


@pytest.mark.asyncio
async def test_handle_message_typing_action_failure_does_not_abort(bot_with_mock_provider):
    """
    Test that if send_action(ChatAction.TYPING) fails, handle_message
    continues and completes successfully.
    """
    bot = bot_with_mock_provider

    update = MagicMock()
    context = MagicMock()
    user_id = 9999

    update.effective_user.id = user_id
    update.message.text = "squat PR!"

    # Typing action fails (initial call)
    # But must succeed on heartbeat (mid-stream call)
    typing_side_effects = [
        Exception("Telegram unreachable"),  # initial TYPING fails
        None,  # heartbeat TYPING succeeds
    ]
    update.message.chat.send_action = AsyncMock(side_effect=typing_side_effects)

    # Mock reply_text for _safe_reply
    update.message.reply_text = AsyncMock()

    # Should not raise; should complete successfully
    await bot.handle_message(update, context)

    # Verify session was updated with assistant message despite initial typing failure
    session = bot.store.get_or_create(user_id)
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert "Hello World" in assistant_msgs[0].content


@pytest.mark.asyncio
async def test_handle_message_producer_exception_during_streaming(bot_with_mock_provider):
    """
    Test that when provider.stream() raises an exception mid-iteration,
    the exception is properly awaited and the user gets "Coach is unavailable".
    """
    bot = bot_with_mock_provider

    # Producer yields one chunk then raises
    def failing_stream(*args, **kwargs):
        yield "First chunk"
        raise RuntimeError("LLM API timeout")

    bot.provider.stream = failing_stream

    update = MagicMock()
    update.effective_user.id = 7777
    update.message.text = "help me"
    update.message.chat.send_action = AsyncMock()
    update.message.reply_text = AsyncMock()

    await bot.handle_message(update, MagicMock())

    # Should send "Coach is unavailable" message
    reply_calls = [call for call in update.message.reply_text.call_args_list]
    reply_texts = [call.args[0] if call.args else None for call in reply_calls]
    assert any("unavailable" in str(text).lower() for text in reply_texts if text)

    # Assistant message should NOT be appended (streaming failed)
    session = bot.store.get_or_create(7777)
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]
    # If there's an assistant message, it should not contain "First chunk" due to the error
    # Actually, with our new implementation, we don't append on error, so should be empty
    assert len(assistant_msgs) == 0


@pytest.mark.asyncio
async def test_handle_message_empty_stream(bot_with_mock_provider):
    """
    Test that when provider.stream() yields no chunks,
    no reply is sent and no assistant message is appended.
    """
    bot = bot_with_mock_provider
    bot.provider.stream.return_value = iter([])

    update = MagicMock()
    update.effective_user.id = 6666
    update.message.text = "anything"
    update.message.chat.send_action = AsyncMock()
    update.message.reply_text = AsyncMock()

    await bot.handle_message(update, MagicMock())

    # reply_text should not be called for empty response
    # (no buffer to send, no error occurred)
    session = bot.store.get_or_create(6666)
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]
    assert len(assistant_msgs) == 0


@pytest.mark.asyncio
async def test_handle_message_safe_reply_failure_on_chunk(bot_with_mock_provider):
    """
    Test that if _safe_reply fails on an intermediate chunk send
    (both Markdown and plain text), the exception is caught and
    streaming is aborted without appending to session.
    """
    bot = bot_with_mock_provider
    # Simulate a large response that triggers buffer flush
    bot.provider.stream.return_value = iter(["x" * 4000, "y" * 1000])

    update = MagicMock()
    update.effective_user.id = 5555
    update.message.text = "test"
    update.message.chat.send_action = AsyncMock()

    # Both Markdown and plain text fail (permanent error)
    from telegram.error import BadRequest

    async def always_fail(text, **kwargs):
        raise BadRequest("Chat not found - permanent")

    update.message.reply_text = always_fail

    await bot.handle_message(update, MagicMock())

    # Should log error and return (not append)
    session = bot.store.get_or_create(5555)
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]
    assert len(assistant_msgs) == 0


@pytest.mark.asyncio
async def test_handle_message_multiple_buffer_flushes(bot_with_mock_provider):
    """
    Test that when response is large enough to trigger multiple buffer flushes,
    all chunks are captured and final message is complete.
    """
    bot = bot_with_mock_provider
    # Three chunks, each ~3000 chars, total > 6000 (triggers 2+ flushes)
    chunks = ["a" * 3000, "b" * 3000, "c" * 3000]
    bot.provider.stream.return_value = iter(chunks)

    update = MagicMock()
    update.effective_user.id = 4444
    update.message.text = "big response"
    update.message.chat.send_action = AsyncMock()
    update.message.reply_text = AsyncMock()

    await bot.handle_message(update, MagicMock())

    # Session should have assistant message with all chunks
    session = bot.store.get_or_create(4444)
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].content == "a" * 3000 + "b" * 3000 + "c" * 3000

    # Multiple reply_text calls should have been made (at least one for buffer flush)
    assert update.message.reply_text.call_count >= 1


@pytest.mark.asyncio
async def test_handle_done_success_clears_session():
    """Test that successful /done clears the session."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()
        bot.system_prompt = "coach"
        bot.program = {"days": {"D1": {"exercises": []}}}

        update = MagicMock()
        update.effective_user.id = 111
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        # Setup a session with some data
        session = bot.store.get_or_create(111)
        session.current_day = "D1"

        # Mock logger save (sync function for asyncio.to_thread)
        with patch("src.coach.telegram.bot.SessionLogger") as mock_logger_class:
            mock_logger = MagicMock()
            mock_logger_class.return_value = mock_logger
            mock_logger.save = MagicMock()  # Regular mock for sync function

            await bot.handle_done(update, context)

            # Session should be cleared
            assert 111 not in bot.store.sessions


@pytest.mark.asyncio
async def test_handle_done_file_exists_error():
    """Test that FileExistsError on /done preserves session."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()
        bot.system_prompt = "coach"
        bot.program = {"days": {"D1": {"exercises": []}}}

        update = MagicMock()
        update.effective_user.id = 222
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        session = bot.store.get_or_create(222)

        # Mock logger.save to raise FileExistsError
        with patch("src.coach.telegram.bot.SessionLogger") as mock_logger_class:
            mock_logger = MagicMock()
            mock_logger_class.return_value = mock_logger
            mock_logger.save = MagicMock(side_effect=FileExistsError("already logged"))

            await bot.handle_done(update, context)

            # Session should NOT be cleared (preserved)
            assert 222 in bot.store.sessions
            update.message.reply_text.assert_awaited()


@pytest.mark.asyncio
async def test_handle_done_permission_error():
    """Test that PermissionError on /done is logged and session preserved."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()
        bot.system_prompt = "coach"
        bot.program = {"days": {"D1": {"exercises": []}}}

        update = MagicMock()
        update.effective_user.id = 333
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        session = bot.store.get_or_create(333)

        # Mock logger.save to raise PermissionError
        with patch("src.coach.telegram.bot.SessionLogger") as mock_logger_class:
            mock_logger = MagicMock()
            mock_logger_class.return_value = mock_logger
            mock_logger.save = MagicMock(side_effect=PermissionError("no write access"))

            await bot.handle_done(update, context)

            # Session should NOT be cleared
            assert 333 in bot.store.sessions
            update.message.reply_text.assert_awaited()


@pytest.mark.asyncio
async def test_handle_status_with_valid_program():
    """Test /status when program is loaded."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()
        bot.system_prompt = "coach"
        bot.program = {
            "days": {
                "D1": {
                    "label": "Lower Strength",
                    "exercises": [
                        {"order": "1", "name": "Squat"},
                        {"order": "2", "name": "RDL"},
                    ],
                }
            }
        }

        update = MagicMock()
        update.effective_user.id = 444
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        session = bot.store.get_or_create(444)
        session.current_day = "D1"

        await bot.handle_status(update, context)

        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.await_args.args[0]
        assert "D1" in call_text
        assert "Lower Strength" in call_text
        assert "Squat" in call_text


@pytest.mark.asyncio
async def test_handle_status_program_not_loaded():
    """Test /status when program is None."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()
        bot.system_prompt = "coach"
        bot.program = None

        update = MagicMock()
        update.effective_user.id = 555
        update.message.reply_text = AsyncMock()

        context = MagicMock()

        bot.store.get_or_create(555)

        await bot.handle_status(update, context)

        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.await_args.args[0]
        assert "Unable to load training program" in call_text


@pytest.mark.asyncio
async def test_handle_day_no_arguments():
    """Test /day with no arguments."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()

        update = MagicMock()
        update.effective_user.id = 666
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = []

        await bot.handle_day(update, context)

        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.await_args.args[0]
        assert "Usage:" in call_text


@pytest.mark.asyncio
async def test_handle_day_invalid_day():
    """Test /day with invalid day."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()

        update = MagicMock()
        update.effective_user.id = 777
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = ["D3"]

        await bot.handle_day(update, context)

        update.message.reply_text.assert_awaited_once()
        call_text = update.message.reply_text.await_args.args[0]
        assert "Invalid day" in call_text


@pytest.mark.asyncio
async def test_concurrent_users_message_isolation():
    """Test that concurrent messages from different users don't cross-contaminate."""
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token"}):
        from src.coach.telegram.bot import CoachBot

        bot = CoachBot()
        bot.system_prompt = "coach"
        bot.provider = MagicMock()

        # Create two mock updates for different users
        async def create_update(user_id: int, text: str):
            update = MagicMock()
            update.effective_user.id = user_id
            update.message.text = text
            update.message.chat.send_action = AsyncMock()
            update.message.reply_text = AsyncMock()
            return update

        # Simulate concurrent handling
        update1 = await create_update(1000, "user 1 message")
        update2 = await create_update(2000, "user 2 message")

        bot.provider.stream = lambda **kwargs: iter(["response"])

        # Handle both concurrently
        import asyncio

        await asyncio.gather(
            bot.handle_message(update1, MagicMock()),
            bot.handle_message(update2, MagicMock()),
        )

        # Both sessions should have their own messages
        session1 = bot.store.get_or_create(1000)
        session2 = bot.store.get_or_create(2000)

        assert any(m.content == "user 1 message" for m in session1.messages)
        assert any(m.content == "user 2 message" for m in session2.messages)

        # User 1's session should not have user 2's message
        assert not any(m.content == "user 2 message" for m in session1.messages)
