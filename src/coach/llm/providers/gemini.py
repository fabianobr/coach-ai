"""Google Gemini provider."""

from typing import Iterator

from ..base import LLMConfig, LLMProvider, Message


class GeminiProvider(LLMProvider):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError(
                "Install google-generativeai: pip install google-generativeai"
            ) from e

        genai.configure(api_key=config.api_key)
        generation_config = {
            "max_output_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        self._genai = genai
        self._model = genai.GenerativeModel(
            model_name=config.model,
            generation_config=generation_config,
        )

    def _build_history(self, messages: list[Message]) -> tuple[list[dict], str]:
        """Split messages into Gemini history + last user message."""
        history = []
        for msg in messages[:-1]:
            role = "model" if msg.role == "assistant" else "user"
            history.append({"role": role, "parts": [msg.content]})
        last = messages[-1].content if messages else ""
        return history, last

    def chat(self, messages: list[Message], system: str | None = None) -> str:
        history, last_message = self._build_history(messages)
        # Prepend system prompt to first user message if provided
        if system and history:
            history[0]["parts"][0] = f"{system}\n\n{history[0]['parts'][0]}"
        elif system:
            last_message = f"{system}\n\n{last_message}"

        chat = self._model.start_chat(history=history)
        response = chat.send_message(last_message)
        return response.text

    def stream(self, messages: list[Message], system: str | None = None) -> Iterator[str]:
        history, last_message = self._build_history(messages)
        if system and history:
            history[0]["parts"][0] = f"{system}\n\n{history[0]['parts'][0]}"
        elif system:
            last_message = f"{system}\n\n{last_message}"

        chat = self._model.start_chat(history=history)
        for chunk in chat.send_message(last_message, stream=True):
            if chunk.text:
                yield chunk.text
