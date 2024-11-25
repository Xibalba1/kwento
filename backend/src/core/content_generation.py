# backend/src/kwento_backend/core/content_generation.py

import json
import random
import logging
from typing import Dict, Any
from services import openai_service
from api.models.book_models import Book
from api.models.helpers import assign_book_model_relationships
from core.prompts import prompts as pt
from core.image_generation import generate_page_illustrations

logger = logging.getLogger(__name__)


async def generate_book(theme: str) -> Book:
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
    # Optionally, store or associate illustrations with the book
    # For example, add image URLs to each page
    for page_number, image_data in illustrations.items():
        page = next((p for p in book.pages if p.page_number == page_number), None)
        if page:
            page.content.illustration_image = image_data[
                "image_data"
            ]  # Store the image URL

    return book


async def generate_illustrations(book: Book) -> Dict[int, Any]:

    illustrations = await generate_page_illustrations(book)
    return illustrations
