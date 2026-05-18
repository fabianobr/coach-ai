"""LLM provider abstraction layer."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Literal


@dataclass
class Message:
    role: Literal["user", "assistant", "system"]
    content: str


@dataclass
class LLMConfig:
    provider: str          # anthropic | openai | ollama | gemini
    model: str
    api_key: str | None = None
    base_url: str | None = None
    max_tokens: int = 2048
    temperature: float = 0.7
    extra: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """Base interface every provider must implement."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    def chat(self, messages: list[Message], system: str | None = None) -> str:
        """Send messages and return the full response text."""
        ...

    @abstractmethod
    def stream(self, messages: list[Message], system: str | None = None) -> Iterator[str]:
        """Send messages and yield response text chunks as they arrive."""
        ...

    @property
    def supports_audio_transcription(self) -> bool:
        """Whether this provider can transcribe audio."""
        return False

    def transcribe_audio(self, file_path: str, mime_type: str | None = None) -> str:
        """Transcribe an audio file to text.

        Args:
            file_path: Path to the audio file (should be WAV format).
            mime_type: MIME type of the audio file (optional).

        Returns:
            Transcribed text.

        Raises:
            NotImplementedError: If provider does not support audio transcription.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support audio transcription"
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.config.model!r})"
