import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


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
    session = store.get_or_create(789)
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
