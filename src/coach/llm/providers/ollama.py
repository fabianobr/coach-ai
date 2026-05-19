"""Ollama provider — uses Ollama's OpenAI-compatible API at /v1."""

import json
import os
import urllib.request
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

    Audio transcription calls Ollama's native POST /api/transcribe endpoint
    using Python's stdlib urllib — no openai package required.
    Pull the model first: `ollama pull whisper`
    Override via OLLAMA_WHISPER_MODEL env var or config.extra["whisper_model"].
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
        # Derive the Ollama root URL (strip /v1 if present) for the native API
        effective = (config.base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._ollama_root = effective[:-3] if effective.endswith("/v1") else effective

    def chat(self, messages: list[Message], system: str | None = None) -> str:
        return self._delegate.chat(messages, system)

    def stream(self, messages: list[Message], system: str | None = None) -> Iterator[str]:
        return self._delegate.stream(messages, system)

    @property
    def supports_audio_transcription(self) -> bool:
        return True

    def transcribe_audio(self, file_path: str, mime_type: str | None = None) -> str:
        """Transcribe audio via Ollama's native /api/transcribe endpoint (no openai SDK)."""
        boundary = "----OllamaTranscribeBoundary"
        filename = os.path.basename(file_path)
        content_type = mime_type or "audio/wav"

        with open(file_path, "rb") as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="model"\r\n\r\n'
            f"{self._whisper_model}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            f"{self._ollama_root}/api/transcribe",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        return result["text"]
