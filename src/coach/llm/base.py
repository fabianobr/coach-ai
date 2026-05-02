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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.config.model!r})"
