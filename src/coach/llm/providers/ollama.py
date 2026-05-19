"""Ollama provider — uses Ollama's OpenAI-compatible API at /v1."""

import os
from typing import Iterator

from ..base import LLMConfig, LLMProvider, Message
from .openai import OpenAIProvider

_DEFAULT_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_WHISPER_MODEL = "whisper"


class OllamaProvider(LLMProvider):
    """
    Delegates to OpenAIProvider pointed at the local Ollama server.
    Ollama exposes an OpenAI-compatible endpoint at /v1, so no extra SDK needed.

    Default base_url: http://localhost:11434/v1
    Override via LLM_BASE_URL env var or config.base_url.

    Audio transcription uses Ollama's Whisper model via the OpenAI-compatible
    /v1/audio/transcriptions endpoint. Pull the model first: `ollama pull whisper`.
    Override the whisper model via OLLAMA_WHISPER_MODEL or config.extra["whisper_model"].
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
        self._whisper_model = (
            config.extra.get("whisper_model")
            or os.getenv("OLLAMA_WHISPER_MODEL", _DEFAULT_WHISPER_MODEL)
        )

    def chat(self, messages: list[Message], system: str | None = None) -> str:
        return self._delegate.chat(messages, system)

    def stream(self, messages: list[Message], system: str | None = None) -> Iterator[str]:
        return self._delegate.stream(messages, system)

    @property
    def supports_audio_transcription(self) -> bool:
        return True

    def transcribe_audio(self, file_path: str, mime_type: str | None = None) -> str:
        with open(file_path, "rb") as f:
            transcript = self._delegate._client.audio.transcriptions.create(
                model=self._whisper_model,
                file=f,
            )
        return transcript.text
