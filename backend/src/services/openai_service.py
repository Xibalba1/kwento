# backend/src/services/openai_service.py
"""
Service module for interacting with OpenAI's API to generate text responses and images
based on provided prompts. This module includes asynchronous functions for generating
content and handling errors with logging.

Functions:
    get_book_response(prompt_content: str) -> Optional[Dict[str, Any]]:
        Generates a book-like response based on the given prompt content using the OpenAI API.
    generate_image(prompt: str) -> Optional[Dict[str, Any]]:
        Generates an image based on the given prompt using OpenAI's image generation API with retries.
    fetch_image(url: str) -> Image.Image:
        Fetches an image from a specified URL and returns it as a PIL Image object.
"""
import openai
import base64
from typing import Optional, Dict, Any

# import time
import asyncio
import time
from asyncio import sleep
import requests
from PIL import Image
import io
from fastapi import HTTPException

from config import settings
from utils.general_utils import get_logger

# initialize logger for this module
logger = get_logger(__name__)

# Set the OpenAI API key from configuration
openai.api_key = settings.openai_api_key


def _is_gpt_image_model(model_name: str) -> bool:
    m = (model_name or "").strip().lower()
    return m.startswith("gpt-image")


def _is_dalle3_model(model_name: str) -> bool:
    return (model_name or "").strip().lower() == "dall-e-3"


def _is_dalle2_model(model_name: str) -> bool:
    return (model_name or "").strip().lower() == "dall-e-2"


def _resolve_openai_image_size(model_name: str, image_kind: str = "page") -> str:
    if image_kind == "cover":
        return "1024x1024"

    override = settings.openai_image_size_override
    if override:
        return override

    profile = settings.openai_image_aspect_profile
    if profile == "square":
        return "1024x1024"

    if _is_gpt_image_model(model_name):
        return "1024x1536"
    if _is_dalle3_model(model_name):
        return "1024x1792"
    if _is_dalle2_model(model_name):
        return "1024x1024"

    # Conservative fallback for unknown models.
    return "1024x1024"


def _resolve_openai_image_quality(model_name: str) -> str:
    mode = settings.openai_image_quality_mode
    if mode != "medium_model_aware":
        return mode

    if _is_gpt_image_model(model_name):
        return "medium"
    if _is_dalle3_model(model_name):
        return "standard"
    if _is_dalle2_model(model_name):
        return "standard"
    return "auto"


def _resolve_openai_reference_edit_quality() -> str:
    return settings.openai_image_reference_edit_quality


def _validate_openai_image_params(model_name: str, size: str, quality: str) -> None:
    model_name = (model_name or "").strip().lower()
    size = (size or "").strip()
    quality = (quality or "").strip().lower()

    if _is_gpt_image_model(model_name):
        allowed_sizes = {"1024x1024", "1024x1536", "1536x1024"}
        allowed_quality = {"auto", "low", "medium", "high"}
    elif _is_dalle3_model(model_name):
        allowed_sizes = {"1024x1024", "1024x1792", "1792x1024"}
        allowed_quality = {"standard", "hd"}
    elif _is_dalle2_model(model_name):
        allowed_sizes = {"256x256", "512x512", "1024x1024"}
        allowed_quality = {"standard"}
    else:
        # Unknown model: allow through so service can error with authoritative message.
        return

    if size not in allowed_sizes:
        raise ValueError(
            f"Unsupported OpenAI image size '{size}' for model '{model_name}'. "
            f"Allowed sizes: {sorted(allowed_sizes)}"
        )
    if quality not in allowed_quality:
        raise ValueError(
            f"Unsupported OpenAI image quality '{quality}' for model '{model_name}'. "
            f"Allowed qualities: {sorted(allowed_quality)}"
        )


def _build_openai_image_request_kwargs(
    prompt: str, model_name: str, image_kind: str = "page"
) -> Dict[str, Any]:
    size = _resolve_openai_image_size(model_name, image_kind=image_kind)
    quality = _resolve_openai_image_quality(model_name)
    _validate_openai_image_params(model_name, size, quality)

    request_kwargs: Dict[str, Any] = {
        "model": model_name,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": quality,
    }

    response_mode = settings.openai_image_output_format
    if _is_gpt_image_model(model_name):
        # GPT Image API uses output_format for png/jpeg/webp and returns base64 by default.
        if response_mode == "url":
            raise ValueError(
                f"Unsupported OpenAI output mode '{response_mode}' for model '{model_name}'. "
                "Use one of: b64_json, png, jpeg, webp."
            )
        if response_mode in {"png", "jpeg", "webp"}:
            request_kwargs["output_format"] = response_mode
    elif _is_dalle3_model(model_name) or _is_dalle2_model(model_name):
        # DALL·E endpoints use response_format with b64_json/url.
        if response_mode not in {"b64_json", "url"}:
            raise ValueError(
                f"Unsupported OpenAI output mode '{response_mode}' for model '{model_name}'. "
                "Use one of: b64_json, url."
            )
        request_kwargs["response_format"] = response_mode
    else:
        # Unknown model; keep prior default behavior.
        if response_mode in {"b64_json", "url"}:
            request_kwargs["response_format"] = response_mode
        else:
            request_kwargs["output_format"] = response_mode

    compression = settings.openai_image_output_compression
    if compression is not None:
        request_kwargs["output_compression"] = compression

    background = settings.openai_image_background
    if background:
        request_kwargs["background"] = background

    logger.info(
        "OpenAI image request params | openai_image_request=%s",
        {
            "model": model_name,
            "image_kind": image_kind,
            "size": size,
            "quality": quality,
            "response_mode": response_mode,
            "output_compression": compression,
            "background": background,
        },
    )
    return request_kwargs


def _build_openai_reference_edit_request_kwargs(
    *,
    prompt: str,
    reference_image_b64: str,
    model_name: str,
    image_kind: str,
) -> Dict[str, Any]:
    size = _resolve_openai_image_size(model_name, image_kind=image_kind)
    quality = _resolve_openai_reference_edit_quality()
    input_fidelity = settings.openai_image_reference_edit_input_fidelity

    request_kwargs: Dict[str, Any] = {
        "model": model_name,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{reference_image_b64}",
                    },
                ],
            }
        ],
        "tools": [
            {
                "type": "image_generation",
                "action": "edit",
                "input_fidelity": input_fidelity,
                "size": size,
                "quality": quality,
            }
        ],
    }
    logger.info(
        "OpenAI reference edit request params | openai_reference_edit_request=%s",
        {
            "model": model_name,
            "image_kind": image_kind,
            "size": size,
            "quality": quality,
            "input_fidelity": input_fidelity,
            "tool_type": "image_generation",
            "tool_action": "edit",
        },
    )
    return request_kwargs


def _extract_image_b64_from_responses_output(response: Any) -> str:
    output_items = getattr(response, "output", None) or []
    for item in output_items:
        item_type = getattr(item, "type", None)
        if item_type is None and isinstance(item, dict):
            item_type = item.get("type")
        if item_type != "image_generation_call":
            continue
        result = getattr(item, "result", None)
        if result is None and isinstance(item, dict):
            result = item.get("result")
        if isinstance(result, str) and result:
            return result
        if isinstance(result, list):
            for entry in result:
                if isinstance(entry, str) and entry:
                    return entry
                if isinstance(entry, dict):
                    value = entry.get("b64_json") or entry.get("data")
                    if isinstance(value, str) and value:
                        return value
    raise ValueError("OpenAI reference-edit response did not include image output.")


async def get_book_response(
    prompt_content: str, model: Optional[str] = None
) -> str:
    result = await get_book_response_with_metadata(
        prompt_content=prompt_content,
        model=model,
    )
    return result["content"]


async def get_book_response_with_metadata(
    prompt_content: str, model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates a response based on the given prompt content using OpenAI's Chat API.

    Args:
        prompt_content (str): The input text prompt for generating a book-like response.

    Returns:
        str: Generated message content as a JSON string if successful.

    Raises:
        HTTPException: Raised with a 500 status code if OpenAI API fails.
    """
    try:
        start = time.monotonic()
        response = await asyncio.to_thread(
            openai.chat.completions.create,
            messages=[
                {
                    "role": "user",
                    "content": prompt_content,
                }
            ],
            response_format={"type": "json_object"},
            model=model or settings.openai_text_model,
        )
        msg_content = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        usage_dict = None
        if usage is not None:
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
        return {
            "content": msg_content,
            "provider": "openai",
            "model": getattr(response, "model", None) or model or settings.openai_text_model,
            "response_id": getattr(response, "id", None),
            "usage": usage_dict,
            "latency_seconds": round(time.monotonic() - start, 3),
        }
    except openai.OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generating book content: {e}"
        )


async def generate_image(
    prompt: str, model: Optional[str] = None, image_kind: str = "page"
) -> Optional[Dict[str, Any]]:
    """
    Generates an image based on a given prompt using OpenAI's Image API with retry logic.

    Args:
        prompt (str): The input text prompt for image generation.

    Returns:
        Optional[Dict[str, Any]]: The API response with image data if successful,
                                  None if an error occurs after retries.

    Raises:
        HTTPException: Raised with a 500 status code if the image generation fails after retries.
    """
    max_retries = 3
    retry_delay_secs = 5
    selected_model = model or settings.openai_image_model
    request_kwargs = _build_openai_image_request_kwargs(
        prompt=prompt,
        model_name=selected_model,
        image_kind=image_kind,
    )
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                openai.images.generate,
                **request_kwargs,
            )
            return response
        except ValueError as e:
            logger.error(f"Invalid OpenAI image request configuration: {e}")
            raise HTTPException(
                status_code=500, detail=f"Invalid OpenAI image configuration: {e}"
            )
        except (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
            openai.RateLimitError,
        ) as e:
            # Log retry attempt details if an error occurs
            logger.error(
                f"Error generating image: {e}. Retrying ({attempt + 1}/{max_retries})..."
            )
            await sleep(retry_delay_secs)
    # Raise HTTPException if all retries fail
    raise HTTPException(
        status_code=500, detail=f"Error generating image after retries."
    )


async def generate_image_with_references(
    prompt: str,
    reference_images: list[bytes],
    model: Optional[str] = None,
    image_kind: str = "page",
) -> Dict[str, Any]:
    if not reference_images:
        raise HTTPException(
            status_code=500,
            detail="Reference-edit generation requires at least one reference image.",
        )

    max_retries = 3
    retry_delay_secs = 5
    selected_model = (
        model or settings.openai_image_reference_edit_model or settings.openai_image_model
    )
    reference_b64 = base64.b64encode(reference_images[0]).decode("utf-8")
    request_kwargs = _build_openai_reference_edit_request_kwargs(
        prompt=prompt,
        reference_image_b64=reference_b64,
        model_name=selected_model,
        image_kind=image_kind,
    )

    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(
                openai.responses.create,
                **request_kwargs,
            )
            image_b64 = _extract_image_b64_from_responses_output(response)
            return {
                "image_bytes": base64.b64decode(image_b64),
                "metadata": {
                    "generation_mode": "reference_edit",
                    "reference_image_count": len(reference_images),
                    "tool_type": "image_generation",
                    "tool_action": "edit",
                    "input_fidelity": settings.openai_image_reference_edit_input_fidelity,
                    "quality": settings.openai_image_reference_edit_quality,
                    "response_id": getattr(response, "id", None),
                    "model": getattr(response, "model", None) or selected_model,
                },
            }
        except ValueError as e:
            logger.error(f"Invalid OpenAI reference-edit response: {e}")
            raise HTTPException(
                status_code=500, detail=f"Invalid OpenAI reference-edit response: {e}"
            )
        except (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
            openai.RateLimitError,
        ) as e:
            logger.error(
                "Error generating reference-edit image: %s. Retrying (%s/%s)...",
                e,
                attempt + 1,
                max_retries,
            )
            await sleep(retry_delay_secs)
    raise HTTPException(
        status_code=500, detail="Error generating reference-edit image after retries."
    )


async def fetch_image(url: str) -> Image.Image:
    """
    Fetches an image from a specified URL, returning it as a PIL Image object.

    Args:
        url (str): The URL of the image to be fetched.

    Returns:
        Image.Image: The fetched image in PIL format.

    Raises:
        HTTPException: Raised with a 500 status code if the image retrieval fails.
    """
    try:
        response = requests.get(url, timeout=10)  # Set timeout for network request
        response.raise_for_status()  # Raise an error if the request was unsuccessful
        image_stream = io.BytesIO(
            response.content
        )  # Create an in-memory stream for the image
        image = Image.open(image_stream)
        return image
    except requests.RequestException as e:
        logger.error(f"Error fetching image: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching image: {e}")
