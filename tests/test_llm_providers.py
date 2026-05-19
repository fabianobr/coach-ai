"""Tests for individual LLM providers — all external SDKs are mocked."""

import pytest
from unittest.mock import MagicMock, patch

from src.coach.llm.base import LLMConfig, Message


def _msgs(*contents: str) -> list[Message]:
    return [Message(role="user", content=c) for c in contents]


# ──────────────────────────────────────────────────────────────────────────────
# Anthropic
# ──────────────────────────────────────────────────────────────────────────────

class TestAnthropicProvider:
    def _make_provider(self):
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from src.coach.llm.providers.anthropic import AnthropicProvider
            cfg = LLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001", api_key="fake")
            provider = AnthropicProvider(cfg)
        provider._client = mock_client
        return provider, mock_client

    def test_chat_returns_text(self):
        provider, client = self._make_provider()
        client.messages.create.return_value.content = [MagicMock(text="squat cues here")]
        result = provider.chat(_msgs("give me squat cues"))
        assert result == "squat cues here"

    def test_chat_passes_system_prompt(self):
        provider, client = self._make_provider()
        client.messages.create.return_value.content = [MagicMock(text="ok")]
        provider.chat(_msgs("hello"), system="You are a coach.")
        call_kwargs = client.messages.create.call_args[1]
        assert call_kwargs["system"] == "You are a coach."

    def test_chat_no_system_omits_key(self):
        provider, client = self._make_provider()
        client.messages.create.return_value.content = [MagicMock(text="ok")]
        provider.chat(_msgs("hello"))
        call_kwargs = client.messages.create.call_args[1]
        assert "system" not in call_kwargs

    def test_stream_yields_chunks(self):
        provider, client = self._make_provider()
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.text_stream = iter(["chunk1", "chunk2"])
        client.messages.stream.return_value = mock_stream
        chunks = list(provider.stream(_msgs("stream test")))
        assert chunks == ["chunk1", "chunk2"]

    def test_missing_sdk_raises(self):
        with patch.dict("sys.modules", {"anthropic": None}):
            with pytest.raises(ImportError, match="pip install anthropic"):
                from importlib import import_module
                import importlib
                import src.coach.llm.providers.anthropic as mod
                importlib.reload(mod)
                cfg = LLMConfig(provider="anthropic", model="x", api_key="k")
                mod.AnthropicProvider(cfg)

    def test_supports_audio_transcription_false(self):
        provider, client = self._make_provider()
        assert provider.supports_audio_transcription is False

    def test_transcribe_audio_raises(self):
        provider, client = self._make_provider()
        with pytest.raises(NotImplementedError):
            provider.transcribe_audio("fake.wav")


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI
# ──────────────────────────────────────────────────────────────────────────────

class TestOpenAIProvider:
    def _make_provider(self, base_url=None):
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_openai_module.OpenAI.return_value = mock_client
        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from src.coach.llm.providers.openai import OpenAIProvider
            cfg = LLMConfig(provider="openai", model="gpt-4o-mini", api_key="sk-fake", base_url=base_url)
            provider = OpenAIProvider(cfg)
        provider._client = mock_client
        return provider, mock_client

    def test_chat_returns_text(self):
        provider, client = self._make_provider()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="bench cues"))
        ]
        result = provider.chat(_msgs("bench cues?"))
        assert result == "bench cues"

    def test_system_prepended_as_system_role(self):
        provider, client = self._make_provider()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="ok"))
        ]
        provider.chat(_msgs("hi"), system="Be a coach.")
        messages = client.chat.completions.create.call_args[1]["messages"]
        assert messages[0] == {"role": "system", "content": "Be a coach."}

    def test_stream_yields_chunks(self):
        provider, client = self._make_provider()
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="hello "))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="world"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=None))]),
        ]
        client.chat.completions.create.return_value = iter(chunks)
        result = list(provider.stream(_msgs("stream")))
        assert result == ["hello ", "world"]

    def test_base_url_forwarded(self):
        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from src.coach.llm.providers.openai import OpenAIProvider
            cfg = LLMConfig(provider="openai", model="x", api_key="k", base_url="http://proxy/v1")
            OpenAIProvider(cfg)
        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["base_url"] == "http://proxy/v1"

    def test_supports_audio_transcription_true(self):
        provider, client = self._make_provider()
        assert provider.supports_audio_transcription is True

    def test_transcribe_audio_calls_whisper(self, tmp_path):
        provider, client = self._make_provider()
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio data")
        mock_transcript = MagicMock(text="hello world")
        client.audio.transcriptions.create.return_value = mock_transcript
        result = provider.transcribe_audio(str(audio_file))
        assert result == "hello world"
        client.audio.transcriptions.create.assert_called_once()
        call_kwargs = client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["model"] == "whisper-1"


# ──────────────────────────────────────────────────────────────────────────────
# Ollama
# ──────────────────────────────────────────────────────────────────────────────

class TestOllamaProvider:
    def _make_provider(self, base_url=None):
        mock_openai_module = MagicMock()
        mock_client = MagicMock()
        mock_openai_module.OpenAI.return_value = mock_client
        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from src.coach.llm.providers.ollama import OllamaProvider
            cfg = LLMConfig(provider="ollama", model="llama3.2", base_url=base_url)
            provider = OllamaProvider(cfg)
        provider._delegate._client = mock_client
        return provider, mock_client

    def test_uses_default_base_url(self):
        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from src.coach.llm.providers.ollama import OllamaProvider, _DEFAULT_BASE_URL
            cfg = LLMConfig(provider="ollama", model="llama3.2")
            OllamaProvider(cfg)
        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["base_url"] == _DEFAULT_BASE_URL

    def test_custom_base_url(self):
        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI.return_value = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            from src.coach.llm.providers.ollama import OllamaProvider
            cfg = LLMConfig(provider="ollama", model="llama3.2", base_url="http://remote:11434/v1")
            OllamaProvider(cfg)
        call_kwargs = mock_openai_module.OpenAI.call_args[1]
        assert call_kwargs["base_url"] == "http://remote:11434/v1"

    def test_chat_delegates(self):
        provider, client = self._make_provider()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="squat ok"))
        ]
        result = provider.chat(_msgs("test"))
        assert result == "squat ok"

    def test_audio_transcription_not_supported(self, tmp_path):
        provider, client = self._make_provider()
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio data")
        assert provider.supports_audio_transcription is False
        with pytest.raises(NotImplementedError, match="Ollama does not support"):
            provider.transcribe_audio(str(audio_file))


# ──────────────────────────────────────────────────────────────────────────────
# Gemini
# ──────────────────────────────────────────────────────────────────────────────

class TestGeminiProvider:
    def _make_provider(self):
        mock_genai = MagicMock()
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_google = MagicMock()
        mock_google.generativeai = mock_genai
        with patch.dict("sys.modules", {"google": mock_google, "google.generativeai": mock_genai}):
            from src.coach.llm.providers.gemini import GeminiProvider
            cfg = LLMConfig(provider="gemini", model="gemini-2.0-flash", api_key="gkey")
            provider = GeminiProvider(cfg)
        provider._model = mock_model
        return provider, mock_model

    def test_chat_returns_text(self):
        provider, model = self._make_provider()
        mock_chat = MagicMock()
        mock_chat.send_message.return_value.text = "leg press cues"
        model.start_chat.return_value = mock_chat
        result = provider.chat(_msgs("leg press cues?"))
        assert result == "leg press cues"

    def test_system_prepended_to_message(self):
        provider, model = self._make_provider()
        mock_chat = MagicMock()
        mock_chat.send_message.return_value.text = "ok"
        model.start_chat.return_value = mock_chat
        provider.chat(_msgs("hello"), system="Be a coach.")
        sent = mock_chat.send_message.call_args[0][0]
        assert sent.startswith("Be a coach.")

    def test_stream_yields_chunks(self):
        provider, model = self._make_provider()
        mock_chat = MagicMock()
        mock_chat.send_message.return_value = [
            MagicMock(text="row "),
            MagicMock(text="cues"),
            MagicMock(text=None),
        ]
        model.start_chat.return_value = mock_chat
        result = list(provider.stream(_msgs("row cues?")))
        assert result == ["row ", "cues"]

    def test_supports_audio_transcription_false(self):
        provider, model = self._make_provider()
        assert provider.supports_audio_transcription is False

    def test_transcribe_audio_raises(self):
        provider, model = self._make_provider()
        with pytest.raises(NotImplementedError):
            provider.transcribe_audio("fake.wav")
