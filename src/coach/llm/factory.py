"""Factory: build an LLMProvider from config or environment variables."""

import os

from .base import LLMConfig, LLMProvider

# Default models per provider
_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.2",
    "gemini": "gemini-2.0-flash",
}


def config_from_env() -> LLMConfig:
    """
    Build LLMConfig from environment variables.

    Required:
        LLM_PROVIDER   — anthropic | openai | ollama | gemini  (default: anthropic)

    Optional:
        LLM_MODEL      — provider-specific model name
        LLM_API_KEY    — API key (falls back to provider-specific env vars)
        LLM_BASE_URL   — override base URL (useful for ollama or proxies)
        LLM_MAX_TOKENS — max tokens (default: 2048)
        LLM_TEMPERATURE — temperature (default: 0.7)

    Provider-specific API key env vars (fallback if LLM_API_KEY not set):
        ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

    _key_fallbacks = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "ollama": None,
    }
    fallback_var = _key_fallbacks.get(provider)
    api_key = os.getenv("LLM_API_KEY") or (os.getenv(fallback_var) if fallback_var else None)

    return LLMConfig(
        provider=provider,
        model=os.getenv("LLM_MODEL", _DEFAULT_MODELS.get(provider, "")),
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL"),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
    )


def get_provider(config: LLMConfig | None = None) -> LLMProvider:
    """
    Instantiate and return the configured LLM provider.

    Args:
        config: LLMConfig instance. If None, reads from environment variables.

    Returns:
        LLMProvider instance ready to use.

    Raises:
        ValueError: if the provider name is not supported.
    """
    if config is None:
        config = config_from_env()

    match config.provider:
        case "anthropic":
            from .providers.anthropic import AnthropicProvider
            return AnthropicProvider(config)
        case "openai":
            from .providers.openai import OpenAIProvider
            return OpenAIProvider(config)
        case "ollama":
            from .providers.ollama import OllamaProvider
            return OllamaProvider(config)
        case "gemini":
            from .providers.gemini import GeminiProvider
            return GeminiProvider(config)
        case _:
            supported = ", ".join(_DEFAULT_MODELS.keys())
            raise ValueError(
                f"Unsupported provider: {config.provider!r}. "
                f"Supported: {supported}"
            )
