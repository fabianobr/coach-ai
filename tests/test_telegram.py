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


async def test_handle_message_falls_back_to_plain_text_on_bad_markdown(bot_with_mock_provider):
    """
    When Telegram rejects the Markdown-formatted reply_text with BadRequest,
    _safe_reply must retry the same text without parse_mode (plain text),
    and must NOT emit 'Error sending response'.
    """
    bot = bot_with_mock_provider

    # Provider yields a chunk with an unmatched asterisk that triggers BadRequest.
    bot.provider.stream.return_value = iter(["Great job *athlete"])

    mock_message = MagicMock()
    mock_message.text = "Done my sets"
    mock_message.chat = MagicMock()
    mock_message.chat.send_action = AsyncMock()

    call_count = 0

    async def selective_reply(text, **kwargs):
        nonlocal call_count
        call_count += 1
        # First call uses parse_mode="Markdown" — reject it.
        if kwargs.get("parse_mode") == "Markdown":
            raise BadRequest("Can't parse entities")
        # Second call (plain text) should succeed silently.

    mock_message.reply_text = selective_reply

    mock_update = MagicMock()
    mock_update.effective_user.id = 8888
    mock_update.message = mock_message

    await bot.handle_message(mock_update, MagicMock())

    # Two reply_text calls total: one Markdown (rejected), one plain.
    assert call_count == 2

    # The session still has the assistant message (stream succeeded).
    session = bot.store.get_or_create(8888)
    assistant_msgs = [m for m in session.messages if m.role == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].content == "Great job *athlete"
