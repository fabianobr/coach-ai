"""OpenAI provider (also works with any OpenAI-compatible API)."""

from typing import Iterator

from ..base import LLMConfig, LLMProvider, Message


class OpenAIProvider(LLMProvider):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("Install openai: pip install openai") from e

        kwargs = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = OpenAI(**kwargs)

    def _build_messages(self, messages: list[Message], system: str | None) -> list[dict]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        result.extend({"role": m.role, "content": m.content} for m in messages)
        return result

    def chat(self, messages: list[Message], system: str | None = None) -> str:
        response = self._client.chat.completions.create(
            model=self.config.model,
            messages=self._build_messages(messages, system),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        return response.choices[0].message.content

    def stream(self, messages: list[Message], system: str | None = None) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self.config.model,
            messages=self._build_messages(messages, system),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
