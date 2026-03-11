from __future__ import annotations

import asyncio
import base64
import hashlib
import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from PIL import Image

from config import settings
from services import openai_service
from utils.general_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ImageGenerationRequest:
    prompt: str
    reference_images: Optional[List[bytes]] = None
    page_index: Optional[int] = None
    image_kind: str = "page"


@dataclass
class ImageGenerationResponse:
    image_bytes: bytes
    provider: str
    model: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ImageGenerator(Protocol):
    provider: str
    model: str

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        ...


class OpenAIImageGenerator:
    provider = "openai"

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.openai_image_model

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        if request.reference_images:
            reference_edit_model_override = settings.openai_image_reference_edit_model
            response = await openai_service.generate_image_with_references(
                prompt=request.prompt,
                reference_images=request.reference_images,
                model=reference_edit_model_override,
                image_kind=request.image_kind,
            )
            image_bytes = response["image_bytes"]
            metadata = response.get("metadata", {})
            model_used = metadata.get("model") or reference_edit_model_override or self.model
        else:
            response = await openai_service.generate_image(
                request.prompt,
                model=self.model,
                image_kind=request.image_kind,
            )
            image_b64 = response.data[0].b64_json
            image_bytes = base64.b64decode(image_b64)
            metadata = {
                "generation_mode": "text_to_image",
                "reference_image_count": 0,
            }
            model_used = self.model
        return ImageGenerationResponse(
            image_bytes=image_bytes,
            provider=self.provider,
            model=model_used,
            metadata=metadata,
        )


class GoogleImageGenerator:
    provider = "google"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or settings.google_image_model
        self.api_key = api_key or settings.google_genai_api_key
        self._client = self._build_client()

    def _build_client(self):
        try:
            from google import genai
        except Exception as exc:
            raise RuntimeError(
                "google-genai is required for provider='google'. Install it and retry."
            ) from exc

        if self.api_key:
            return genai.Client(api_key=self.api_key)
        return genai.Client()

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        response = await asyncio.to_thread(self._generate_sync, request)
        return ImageGenerationResponse(
            image_bytes=response,
            provider=self.provider,
            model=self.model,
        )

    def _generate_sync(self, request: ImageGenerationRequest) -> bytes:
        self._log_request_observability(request)
        contents: List[Any] = [request.prompt]
        for ref_image_bytes in request.reference_images or []:
            contents.append(Image.open(io.BytesIO(ref_image_bytes)))

        # Ask Gemini explicitly for image output to reduce ambiguous text-only responses.
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=(
                        "1:1"
                        if request.image_kind == "cover"
                        else settings.google_image_aspect_ratio
                    ),
                    image_size=settings.google_image_size,
                ),
            ),
        )
        image_bytes = self._extract_image_bytes(response)
        if not image_bytes:
            summary = self._summarize_response_for_debug(response)
            logger.error(
                "Google image generation returned no image bytes. model=%s summary=%s",
                self.model,
                summary,
            )
            raise ValueError(
                "Google image generation response did not include image bytes."
            )
        return image_bytes

    def _extract_image_bytes(self, response: Any) -> Optional[bytes]:
        # Try the direct convenience surface first.
        for part in getattr(response, "parts", []) or []:
            maybe_bytes = self._part_to_bytes(part)
            if maybe_bytes:
                return maybe_bytes

        # Fallback to candidate/content part layout if present.
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                maybe_bytes = self._part_to_bytes(part)
                if maybe_bytes:
                    return maybe_bytes

        return None

    @staticmethod
    def _part_to_bytes(part: Any) -> Optional[bytes]:
        inline_data = getattr(part, "inline_data", None)
        if inline_data is not None:
            data = getattr(inline_data, "data", None)
            if isinstance(data, bytes):
                return data
            if isinstance(data, bytearray):
                return bytes(data)
            if isinstance(data, str):
                return base64.b64decode(data)

        as_image = getattr(part, "as_image", None)
        if callable(as_image):
            try:
                pil_image = as_image()
            except Exception:
                pil_image = None

            if pil_image is not None and hasattr(pil_image, "save"):
                with io.BytesIO() as output:
                    pil_image.save(output, format="PNG")
                    return output.getvalue()
        return None

    def _summarize_response_for_debug(self, response: Any) -> Dict[str, Any]:
        def _part_summary(part: Any) -> Dict[str, Any]:
            inline_data = getattr(part, "inline_data", None)
            mime_type = getattr(inline_data, "mime_type", None) if inline_data else None
            data = getattr(inline_data, "data", None) if inline_data else None
            text = getattr(part, "text", None)
            has_as_image = callable(getattr(part, "as_image", None))
            as_image_state = "n/a"
            if has_as_image:
                try:
                    as_image_state = (
                        "returns_image"
                        if getattr(part, "as_image")() is not None
                        else "returns_none"
                    )
                except Exception as exc:
                    as_image_state = f"raises:{type(exc).__name__}"
            return {
                "mime_type": mime_type,
                "has_inline_data": inline_data is not None,
                "inline_data_type": type(data).__name__ if data is not None else None,
                "inline_data_len": len(data) if hasattr(data, "__len__") else None,
                "has_text": bool(text),
                "text_preview": (text[:120] if isinstance(text, str) else None),
                "has_as_image": has_as_image,
                "as_image_state": as_image_state,
            }

        summary: Dict[str, Any] = {
            "response_parts_count": len(getattr(response, "parts", []) or []),
            "response_parts": [
                _part_summary(part) for part in (getattr(response, "parts", []) or [])
            ],
            "prompt_feedback": getattr(response, "prompt_feedback", None),
            "candidates_count": len(getattr(response, "candidates", []) or []),
            "candidate_summaries": [],
        }

        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", []) or []
            summary["candidate_summaries"].append(
                {
                    "finish_reason": getattr(candidate, "finish_reason", None),
                    "safety_ratings": getattr(candidate, "safety_ratings", None),
                    "parts_count": len(parts),
                    "parts": [_part_summary(part) for part in parts],
                }
            )

        return summary

    def _log_request_observability(self, request: ImageGenerationRequest) -> None:
        mode = settings.image_prompt_observability_mode
        if mode == "off":
            return

        reference_images = request.reference_images or []
        max_chars = max(0, settings.image_prompt_log_max_chars)
        prompt = request.prompt or ""
        prompt_preview = prompt[:max_chars] if max_chars else ""

        log_payload: Dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "observability_mode": mode,
            "page_index": request.page_index,
            "prompt_char_count": len(prompt),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "reference_image_count": len(reference_images),
            "reference_image_sizes_bytes": [len(img) for img in reference_images],
        }

        if mode == "full":
            log_payload["prompt_sent_to_gemini"] = prompt_preview
            log_payload["prompt_truncated"] = len(prompt_preview) < len(prompt)

        logger.info("Gemini image request payload. | gemini_request=%s", log_payload)


def build_image_generator(provider: Optional[str] = None) -> ImageGenerator:
    selected_provider = provider or settings.image_provider
    if selected_provider == "openai":
        return OpenAIImageGenerator()
    if selected_provider == "google":
        return GoogleImageGenerator()

    raise ValueError(
        f"Unsupported image provider '{selected_provider}'. "
        "Supported providers right now: openai, google."
    )
