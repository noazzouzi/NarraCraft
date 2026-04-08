from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base interface for LLM providers. All providers must implement this."""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt to the LLM and return the text response."""
        ...

    @abstractmethod
    async def generate_json(self, prompt: str, system: str | None = None) -> dict:
        """Send a prompt and parse the response as JSON."""
        ...

    @abstractmethod
    async def check_status(self) -> dict:
        """Return provider status: name, model, configured, remaining RPD if known."""
        ...
