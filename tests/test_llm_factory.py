"""Tests for LLM factory — no real API calls, providers are mocked."""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.coach.llm.base import LLMConfig
from src.coach.llm.factory import config_from_env, get_provider


class TestConfigFromEnv:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        cfg = config_from_env()
        assert cfg.provider == "anthropic"
        assert cfg.model == "claude-haiku-4-5-20251001"

    def test_provider_override(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        cfg = config_from_env()
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o"
        assert cfg.api_key == "sk-test"

    def test_generic_key_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("LLM_API_KEY", "generic-key")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "provider-key")
        cfg = config_from_env()
        assert cfg.api_key == "generic-key"

    def test_provider_specific_key_fallback(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        cfg = config_from_env()
        assert cfg.api_key == "openai-key"

    def test_ollama_no_key_required(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        cfg = config_from_env()
        assert cfg.api_key is None

    def test_max_tokens_and_temperature(self, monkeypatch):
        monkeypatch.setenv("LLM_MAX_TOKENS", "512")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.2")
        cfg = config_from_env()
        assert cfg.max_tokens == 512
        assert cfg.temperature == pytest.approx(0.2)

    def test_base_url(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
        cfg = config_from_env()
        assert cfg.base_url == "http://localhost:11434/v1"

    def test_gemini_default_model(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        cfg = config_from_env()
        assert cfg.model == "gemini-2.0-flash"


class TestGetProvider:
    def _make_config(self, provider: str, **kwargs) -> LLMConfig:
        return LLMConfig(provider=provider, model="test-model", api_key="fake-key", **kwargs)

    def test_unsupported_provider_raises(self):
        cfg = LLMConfig(provider="unknown", model="x")
        with pytest.raises(ValueError, match="Unsupported provider"):
            get_provider(cfg)

    def test_returns_anthropic_provider(self):
        cfg = self._make_config("anthropic")
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            provider = get_provider(cfg)
            from src.coach.llm.providers.anthropic import AnthropicProvider
            assert isinstance(provider, AnthropicProvider)

    def test_returns_openai_provider(self):
        cfg = self._make_config("openai")
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = get_provider(cfg)
            from src.coach.llm.providers.openai import OpenAIProvider
            assert isinstance(provider, OpenAIProvider)

    def test_returns_ollama_provider(self):
        cfg = self._make_config("ollama")
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = get_provider(cfg)
            from src.coach.llm.providers.ollama import OllamaProvider
            assert isinstance(provider, OllamaProvider)

    def test_returns_gemini_provider(self):
        cfg = self._make_config("gemini")
        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value = MagicMock()
        mock_google = MagicMock()
        mock_google.generativeai = mock_genai
        with patch.dict("sys.modules", {"google": mock_google, "google.generativeai": mock_genai}):
            provider = get_provider(cfg)
            from src.coach.llm.providers.gemini import GeminiProvider
            assert isinstance(provider, GeminiProvider)

    def test_none_config_reads_env(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("LLM_API_KEY", "sk-fake")
        mock_openai = MagicMock()
        mock_openai.OpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            provider = get_provider()
            from src.coach.llm.providers.openai import OpenAIProvider
            assert isinstance(provider, OpenAIProvider)
