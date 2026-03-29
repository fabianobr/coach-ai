"""Tests for LLM base types."""

import pytest
from src.coach.llm.base import LLMConfig, Message


class TestMessage:
    def test_user_message(self):
        m = Message(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"

    def test_assistant_message(self):
        m = Message(role="assistant", content="hi there")
        assert m.role == "assistant"

    def test_empty_content(self):
        m = Message(role="user", content="")
        assert m.content == ""


class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig(provider="openai", model="gpt-4o-mini")
        assert cfg.api_key is None
        assert cfg.base_url is None
        assert cfg.max_tokens == 2048
        assert cfg.temperature == 0.7
        assert cfg.extra == {}

    def test_full_config(self):
        cfg = LLMConfig(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            api_key="sk-test",
            base_url="https://api.example.com",
            max_tokens=1024,
            temperature=0.5,
        )
        assert cfg.provider == "anthropic"
        assert cfg.api_key == "sk-test"
        assert cfg.max_tokens == 1024

    def test_extra_field(self):
        cfg = LLMConfig(provider="ollama", model="llama3.2", extra={"seed": 42})
        assert cfg.extra["seed"] == 42
