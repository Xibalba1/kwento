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
from typing import Optional, Dict, Any

# import time
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


async def get_book_response(
    prompt_content: str, model: Optional[str] = None
) -> str:
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
        response = openai.chat.completions.create(
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
        return msg_content
    except openai.OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generating book content: {e}"
        )


async def generate_image(
    prompt: str, model: Optional[str] = None
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
    for attempt in range(max_retries):
        try:
            response = openai.images.generate(
                model=model or settings.openai_image_model,
                prompt=prompt,
                n=1,
                size="1024x1024",
                response_format="b64_json",
            )
            return response
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
