"""Tests for session store LRU eviction and management."""

import pytest

from src.coach.api.session_store import SessionStore
from src.coach.llm import Message


def test_session_store_basic_operations():
    """SessionStore should create and retrieve sessions."""
    store = SessionStore()

    history1 = store.get_or_create("s1")
    history2 = store.get_or_create("s2")

    assert history1 is not history2
    assert len(history1) == 0
    assert len(history2) == 0


def test_session_store_append():
    """SessionStore.append should add messages to session."""
    store = SessionStore()
    msg = Message(role="user", content="test")

    store.append("s1", msg)
    history = store.get_or_create("s1")

    assert len(history) == 1
    assert history[0].content == "test"


def test_session_store_lru_eviction_at_capacity():
    """SessionStore should evict oldest session when at max capacity."""
    store = SessionStore(max_sessions=3)

    # Create 3 sessions
    store.get_or_create("s1")
    store.get_or_create("s2")
    store.get_or_create("s3")

    assert len(store.sessions) == 3

    # 4th session triggers eviction of s1 (oldest)
    store.get_or_create("s4")

    assert "s1" not in store.sessions
    assert "s2" in store.sessions
    assert "s3" in store.sessions
    assert "s4" in store.sessions
    assert len(store.sessions) == 3


def test_session_store_lru_order_preserved():
    """SessionStore should maintain LRU order correctly."""
    store = SessionStore(max_sessions=3)

    s1 = store.get_or_create("s1")
    s2 = store.get_or_create("s2")
    s3 = store.get_or_create("s3")

    # Access s1 again (moves to end)
    _ = store.get_or_create("s1")

    # Add s4 - should evict s2 (oldest active)
    store.get_or_create("s4")

    assert "s2" not in store.sessions
    assert "s1" in store.sessions
    assert "s3" in store.sessions
    assert "s4" in store.sessions


def test_session_store_clear():
    """SessionStore.clear should remove session."""
    store = SessionStore()

    store.append("s1", Message(role="user", content="msg"))
    assert "s1" in store.sessions

    store.clear("s1")
    assert "s1" not in store.sessions


def test_session_store_isolation():
    """Different sessions should be isolated."""
    store = SessionStore()

    msg_a = Message(role="user", content="A")
    msg_b = Message(role="user", content="B")

    store.append("session_a", msg_a)
    store.append("session_b", msg_b)

    history_a = store.get_or_create("session_a")
    history_b = store.get_or_create("session_b")

    assert len(history_a) == 1
    assert len(history_b) == 1
    assert history_a[0].content == "A"
    assert history_b[0].content == "B"


def test_session_store_eviction_with_appends():
    """LRU eviction should work correctly with appends."""
    store = SessionStore(max_sessions=2)

    msg1 = Message(role="user", content="msg1")
    msg2 = Message(role="user", content="msg2")
    msg3 = Message(role="user", content="msg3")

    store.append("s1", msg1)
    store.append("s2", msg2)

    # This should evict s1
    store.append("s3", msg3)

    assert "s1" not in store.sessions
    assert "s2" in store.sessions
    assert "s3" in store.sessions
