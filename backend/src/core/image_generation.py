# backend/src/core/image_generation.py

import json
import logging
from typing import Dict, Any
import base64
import copy

from config import settings
from services import openai_service, image_service
from openai import BadRequestError
from api.models.book_models import Page
from core.prompts import prompts as pt
from utils.general_utils import (
    ensure_directory_exists,
    write_json_file,
    construct_storage_path,
)
from api.models.helpers import remove_book_model_relationships

logger = logging.getLogger(__name__)


def make_illustration_prompt(page: Page) -> str:
    illustration_prompt = pt.PROMPT_PAGE_ILLUSTRATION_BODY.copy()
    illustration_prompt["illustration_style"] = page.book_parent.illustration_style
    illustration_prompt["illustration_description"] = page.content.illustration
    illustration_prompt["characters_in_illustration"] = [
        {"name": cinfo.name, "appearance": cinfo.appearance}
        for cinfo in page.content.characters_in_this_page_data
    ]
    illustration_prompt["text_content"] = page.content.text_content_of_this_page
    illustration_prompt_str = json.dumps(illustration_prompt, indent=1)
    illustration_prompt_str = (
        f"{pt.PROMPT_PAGE_ILLUSTRATION_PREFACE}\n{illustration_prompt_str}"
    )
    return illustration_prompt_str


async def generate_single_page_illustration(
    page: Page, illustration_prompt: str, images_dir: str
) -> Dict[str, Any]:
    """
    Generates an illustration for a single page and saves the image.
    """
    try:
        page.content.illustration_prompt = illustration_prompt

        # Generate the image using OpenAI service
        response = await openai_service.generate_image(illustration_prompt)
        image_b64 = response.data[0].b64_json

        # Decode base64 image data
        image_data = base64.b64decode(image_b64)

        # Construct a normalized filename and path
        filename = f"{page.page_number}.png"
        relative_filepath = f"{images_dir}/{filename}"

        # Save the image
        saved_path = image_service.save_image(image_data, relative_filepath)

        # Update page content
        page.content.illustration = saved_path
        logger.debug(
            f"generate_single_page_illustration(): book.page.illustration set to {saved_path} for page number {page.page_number}"
        )

        # return {"image_data": image_b64}
        return {"image_data": None}
    except BadRequestError as bre:
        if "content_policy_violation" in str(bre):
            raise ValueError(
                f"Content policy violation when generating image: {bre}"
            ) from bre
    except Exception as e:
        logger.error(f"Error generating illustration for page {page.page_number}: {e}")
        raise


async def generate_page_illustrations(book) -> Dict[int, Any]:
    """
    Generates illustrations for all pages in a book and saves them appropriately.
    """
    illustrations = {}
    logger.info(f"Generating illustrations for the book '{book.book_title}'")

    # image_generation.py
    book_id_str = str(book.book_id)
    logger.debug(f"Using book_id for directory names: {book_id_str}")

    # Construct paths using the utility function
    book_dir = construct_storage_path(book_id_str)
    images_dir = construct_storage_path(f"{book_id_str}/images")

    logger.debug(f"Constructed book_dir: {book_dir}")
    logger.debug(f"Constructed images_dir: {images_dir}")

    # Ensure directories exist
    if not settings.use_cloud_storage:
        ensure_directory_exists(book_dir)
        ensure_directory_exists(images_dir)
    logger.info(f"Directories ensured for book '{book.book_title}'")

    # Generate illustrations for each page
    for page in book.pages:
        illustration_prompt = make_illustration_prompt(page)
        image_data = await generate_single_page_illustration(
            page, illustration_prompt, images_dir
        )
        illustrations[page.page_number] = image_data
        logger.info(f"Generated illustration for page {page.page_number}")

    # Save book JSON at the root of book_dir
    book_copy_no_refs = remove_book_model_relationships(copy.deepcopy(book))
    book_data = book_copy_no_refs.dict()

    # metadata to be attached to JSON file in cloud store
    metadata = {
        "book_id": str(book.book_id),
        "book_title": book.book_title,
    }

    filename = f"{book_id_str}.json"
    write_json_file(filename, book_data, relative_path=book_dir, metadata=metadata)
    logger.info(f"Saved book JSON for '{book.book_title}'")

    return illustrations
