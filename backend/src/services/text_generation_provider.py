from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict
from typing import Optional, Protocol

from config import settings
from services import openai_service


class TextGenerator(Protocol):
    provider: str
    model: str

    async def generate_book_response(self, prompt_content: str) -> str:
        ...

    async def generate_book_response_with_metadata(
        self, prompt_content: str
    ) -> "TextGenerationResult":
        ...


@dataclass
class TextGenerationResult:
    content: str
    provider: str
    model: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class OpenAITextGenerator:
    provider = "openai"

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.openai_text_model

    async def generate_book_response(self, prompt_content: str) -> str:
        return await openai_service.get_book_response(
            prompt_content=prompt_content,
            model=self.model,
        )

    async def generate_book_response_with_metadata(
        self, prompt_content: str
    ) -> TextGenerationResult:
        response = await openai_service.get_book_response_with_metadata(
            prompt_content=prompt_content,
            model=self.model,
        )
        return TextGenerationResult(
            content=response.get("content", ""),
            provider=response.get("provider", self.provider),
            model=response.get("model", self.model),
            metadata={
                "response_id": response.get("response_id"),
                "usage": response.get("usage"),
                "latency_seconds": response.get("latency_seconds"),
            },
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

    async def generate_book_response_with_metadata(
        self, prompt_content: str
    ) -> TextGenerationResult:
        started = time.monotonic()
        response = await asyncio.to_thread(
            self._generate_sync_with_metadata, prompt_content
        )
        response["latency_seconds"] = round(time.monotonic() - started, 3)
        return TextGenerationResult(
            content=response.get("content", ""),
            provider=self.provider,
            model=response.get("model", self.model),
            metadata={
                "response_id": response.get("response_id"),
                "usage": response.get("usage"),
                "latency_seconds": response.get("latency_seconds"),
            },
        )

    def _generate_sync(self, prompt_content: str) -> str:
        response = self._generate_sync_with_metadata(prompt_content)
        return response["content"]

    def _generate_sync_with_metadata(self, prompt_content: str) -> Dict[str, Any]:
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
            usage_metadata = getattr(response, "usage_metadata", None)
            usage = None
            if usage_metadata is not None:
                usage = {
                    "prompt_tokens": getattr(
                        usage_metadata, "prompt_token_count", None
                    ),
                    "completion_tokens": getattr(
                        usage_metadata, "candidates_token_count", None
                    ),
                    "total_tokens": getattr(
                        usage_metadata, "total_token_count", None
                    ),
                }
            return {
                "content": text,
                "provider": self.provider,
                "model": self.model,
                "response_id": getattr(response, "response_id", None),
                "usage": usage,
            }

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
