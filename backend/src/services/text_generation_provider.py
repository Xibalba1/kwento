from __future__ import annotations

import asyncio
from typing import Optional, Protocol

from config import settings
from services import openai_service


class TextGenerator(Protocol):
    provider: str
    model: str

    async def generate_book_response(self, prompt_content: str) -> str:
        ...


class OpenAITextGenerator:
    provider = "openai"

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.openai_text_model

    async def generate_book_response(self, prompt_content: str) -> str:
        return await openai_service.get_book_response(
            prompt_content=prompt_content,
            model=self.model,
        )


class GoogleTextGenerator:
    provider = "google"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or settings.google_text_model
        self.api_key = api_key or settings.google_genai_api_key
        self._client = self._build_client()

    def _build_client(self):
        try:
            from google import genai
        except Exception as exc:
            raise RuntimeError(
                "google-genai is required for text provider='google'. Install it and retry."
            ) from exc

        if self.api_key:
            return genai.Client(api_key=self.api_key)
        return genai.Client()

    async def generate_book_response(self, prompt_content: str) -> str:
        return await asyncio.to_thread(self._generate_sync, prompt_content)

    def _generate_sync(self, prompt_content: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt_content,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text

        raise ValueError(
            "Google text generation response did not include text content."
        )


def build_text_generator(provider: Optional[str] = None) -> TextGenerator:
    selected_provider = provider or settings.text_provider
    if selected_provider == "openai":
        return OpenAITextGenerator()
    if selected_provider == "google":
        return GoogleTextGenerator()

    raise ValueError(
        f"Unsupported text provider '{selected_provider}'. "
        "Supported providers right now: openai, google."
    )
