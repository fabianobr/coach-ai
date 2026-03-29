"""Anthropic (Claude) provider."""

from typing import Iterator

from ..base import LLMConfig, LLMProvider, Message


class AnthropicProvider(LLMProvider):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        try:
            import anthropic
        except ImportError as e:
            raise ImportError("Install anthropic: pip install anthropic") from e

        self._client = anthropic.Anthropic(api_key=config.api_key)

    def _build_params(self, messages: list[Message], system: str | None) -> dict:
        params = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            params["system"] = system
        return params

    def chat(self, messages: list[Message], system: str | None = None) -> str:
        response = self._client.messages.create(**self._build_params(messages, system))
        return response.content[0].text

    def stream(self, messages: list[Message], system: str | None = None) -> Iterator[str]:
        with self._client.messages.stream(**self._build_params(messages, system)) as s:
            for text in s.text_stream:
                yield text
