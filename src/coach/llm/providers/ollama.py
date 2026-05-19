"""Ollama provider — uses Ollama's OpenAI-compatible API at /v1."""

from ..base import LLMConfig, LLMProvider, Message
from .openai import OpenAIProvider

_DEFAULT_BASE_URL = "http://localhost:11434/v1"


class OllamaProvider(LLMProvider):
    """
    Delegates to OpenAIProvider pointed at the local Ollama server.
    Ollama exposes an OpenAI-compatible endpoint at /v1, so no extra SDK needed.

    Default base_url: http://localhost:11434/v1
    Override via LLM_BASE_URL env var or config.base_url.
    """

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        ollama_config = LLMConfig(
            provider="openai",
            model=config.model,
            api_key=config.api_key or "ollama",  # Ollama ignores the key
            base_url=config.base_url or _DEFAULT_BASE_URL,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
        self._delegate = OpenAIProvider(ollama_config)

    def chat(self, messages: list[Message], system: str | None = None) -> str:
        return self._delegate.chat(messages, system)

    def stream(self, messages: list[Message], system: str | None = None):
        return self._delegate.stream(messages, system)

    @property
    def supports_audio_transcription(self) -> bool:
        return False

    def transcribe_audio(self, file_path: str, mime_type: str | None = None) -> str:
        raise NotImplementedError("Ollama does not support audio transcription.")
