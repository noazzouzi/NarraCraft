import json
import re

from google import genai

from backend.llm.provider import LLMProvider


class GeminiFlashProvider(LLMProvider):
    """Google Gemini 2.5 Flash via free API tier."""

    MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.configured = bool(api_key)
        if self.configured:
            self.client = genai.Client(api_key=api_key)

    async def generate(self, prompt: str, system: str | None = None) -> str:
        if not self.configured:
            raise RuntimeError("Gemini API key not configured")

        config = {}
        if system:
            config["system_instruction"] = system

        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(**config) if config else None,
        )
        return response.text

    async def generate_json(self, prompt: str, system: str | None = None) -> dict:
        full_prompt = prompt + "\n\nRespond with ONLY a single valid JSON object. No markdown, no commentary, no code fences, no extra text before or after."
        text = await self.generate(full_prompt, system=system)

        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        # Find the outermost JSON object — handle extra text before/after
        # Find first { and last }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1:
            text = text[first_brace:last_brace + 1]

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Log the raw text for debugging
            print(f"JSON parse error: {e}")
            print(f"Raw LLM output (first 500 chars): {text[:500]}")
            raise

    async def check_status(self) -> dict:
        return {
            "provider": "gemini_flash",
            "model": self.MODEL,
            "configured": self.configured,
            "free_tier": True,
            "rpd_limit": 20,
        }


class GeminiFlashLiteProvider(GeminiFlashProvider):
    """Google Gemini 2.5 Flash-Lite via free API tier."""

    MODEL = "gemini-2.5-flash-lite"

    async def check_status(self) -> dict:
        return {
            "provider": "gemini_flash_lite",
            "model": self.MODEL,
            "configured": self.configured,
            "free_tier": True,
            "rpd_limit": 20,
        }
