# backend/src/core/content_generation.py

import json
import random
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from config import settings
from typing import Dict, Any
from services import openai_service
from api.models.book_models import Book
from api.models.helpers import assign_book_model_relationships
from core.prompts import prompts as pt
from core.image_generation import generate_page_illustrations
from utils.general_utils import generate_presigned_url

logger = logging.getLogger(__name__)


async def generate_book(theme: str) -> Book:
    try:
        logger.info(f"Generating book with theme: {theme}")
        # Prepare the prompt
        master_prompt = pt.PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS.format(theme=theme)
        output_example = pt.TEMPLATE_CHILDRENS_BOOK
        prompt_content = f"{master_prompt}\n{output_example}"

        # Get the book response
        assistant_message = await openai_service.get_book_response(prompt_content)

        # Parse the assistant's message into a Book object
        try:
            book_data = json.loads(assistant_message)
            book = Book(**book_data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing book data: {e}")
            raise

        # Assign relationships
        assign_book_model_relationships(book)

        # Set illustration style
        style_attributes = random.choice(pt.ILLUSTRATION_STYLE_ATTRIBUTES)
        book.illustration_style = style_attributes

        # Generate illustrations after creating the book
        illustrations = await generate_illustrations(book)
        expiration_time = timedelta(hours=1)
        expires_at = datetime.now(timezone.utc) + expiration_time

        for page_number, image_data in illustrations.items():
            page = next((p for p in book.pages if p.page_number == page_number), None)
            if page:
                if settings.use_cloud_storage:
                    image_path = f"{book.book_id}/images/{page_number}.png"
                    url = generate_presigned_url(image_path, expiration=3600)
                else:
                    url = str(
                        (
                            Path(settings.local_data_path)
                            / f"{book.book_id}/images/{page_number}.png"
                        ).resolve()
                    )

                # Update illustration with URL and expiration metadata
                page.content.illustration = {
                    "url": url,
                    "expires_at": expires_at,
                }

        return book
    except ValueError as e:
        if "content_policy_violation" in str(e):
            raise
        else:
            raise


async def generate_illustrations(book: Book) -> Dict[int, Any]:

    illustrations = await generate_page_illustrations(book)
    return illustrations
