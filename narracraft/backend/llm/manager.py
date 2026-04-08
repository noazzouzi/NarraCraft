from backend.llm.provider import LLMProvider
from backend.llm.gemini import GeminiFlashProvider, GeminiFlashLiteProvider

# Registry of available providers
PROVIDERS: dict[str, type[LLMProvider]] = {
    "gemini_flash": GeminiFlashProvider,
    "gemini_flash_lite": GeminiFlashLiteProvider,
}

# Singleton instance
_current_provider: LLMProvider | None = None
_current_provider_name: str | None = None


def init_provider(provider_name: str, api_key: str) -> LLMProvider:
    """Initialize or switch the active LLM provider."""
    global _current_provider, _current_provider_name

    if provider_name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(PROVIDERS.keys())}")

    _current_provider = PROVIDERS[provider_name](api_key=api_key)
    _current_provider_name = provider_name
    return _current_provider


def get_provider() -> LLMProvider:
    """Get the current active LLM provider. Raises if not initialized."""
    if _current_provider is None:
        raise RuntimeError("LLM provider not initialized. Configure API key in Settings.")
    return _current_provider


def get_provider_name() -> str | None:
    """Get the name of the current provider."""
    return _current_provider_name


def list_providers() -> list[str]:
    """List all available provider names."""
    return list(PROVIDERS.keys())
