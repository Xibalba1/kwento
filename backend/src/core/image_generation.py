# backend/src/kwento_backend/core/image_generation.py

import json
import logging
from typing import Dict, Any
import base64
from pathlib import Path
import copy

from services import openai_service, image_service
from api.models.book_models import Page
from core.prompts import prompts as pt
from utils.book_utils import book_title_normalize
from utils.general_utils import get_project_root, save_file
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
    page: Page, illustration_prompt: str, images_dir: Path, save_where: str = "local"
) -> Dict[str, Any]:
    """
    Generates an illustration for a single page and saves the image.

    Args:
        page (Page): The page object for which to generate the illustration.
        illustration_prompt (str): The prompt to generate the illustration.
        images_dir (Path): The directory where images should be saved.
        save_where (str): Destination to save the image. Options: "local", "cloud".

    Returns:
        Dict[str, Any]: Dictionary containing image data.
    """
    try:
        page.content.illustration_prompt = illustration_prompt

        response = await openai_service.generate_image(illustration_prompt)
        image_b64 = response.data[0].b64_json

        image_data = base64.b64decode(image_b64)

        # Define the image filename
        filename = f"{page.page_number}.png"

        # Define the relative filepath for saving
        relative_filepath = f"local_data/{book_title_normalize(page.book_parent.book_title, append_datetime=False)}/images/{filename}"

        # Save the image using the image_service
        saved_path = image_service.save_image(
            image_data, relative_filepath, save_where=save_where
        )

        page.content.illustration = saved_path  # saved_path is now a URL or path
        page.content.illustration_b64_data = image_b64

        return {"image_data": image_b64}
    except Exception as e:
        logger.error(f"Error generating illustration for page {page.page_number}: {e}")
        raise


async def generate_page_illustrations(
    book, save_where: str = "local"
) -> Dict[int, Any]:
    """
    Generates illustrations for all pages in a book and saves them appropriately.

    Args:
        book: The book object containing pages and metadata.
        save_where (str): Destination to save the images and JSON. Options: "local", "cloud".

    Returns:
        Dict[int, Any]: Dictionary mapping page numbers to their image data.
    """
    illustrations = {}
    logger.info(f"Generating illustrations for the book '{book.book_title}'")

    # Normalize the book title without appending datetime for consistent directory naming
    book_normalized = book_title_normalize(book.book_title, append_datetime=False)

    # Get the project root
    project_root = get_project_root()

    # Define the base directory for this book
    book_dir = project_root / "local_data" / book_normalized

    # Create the book directory if saving locally
    if save_where == "local":
        book_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory for book at {book_dir}")

    # Define the images directory
    images_dir = book_dir / "images"

    # Create the images directory if saving locally
    if save_where == "local":
        images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created images directory at {images_dir}")

    for page in book.pages:
        illustration_prompt = make_illustration_prompt(page)
        image_data = await generate_single_page_illustration(
            page,
            illustration_prompt,
            (
                images_dir if save_where == "local" else project_root
            ),  # Pass images_dir only if saving locally
            save_where=save_where,
        )
        illustrations[page.page_number] = image_data
        logger.info(f"Generated illustration for page {page.page_number}")

    # Save the book JSON if saving locally
    if save_where == "local":
        book_json_path = book_dir / "book.json"

        # make a copy of the book, strip its relational data, dump it to json, and save it
        book_copy_no_refs = remove_book_model_relationships(copy.deepcopy(book))
        book_json_content = book_copy_no_refs.json(indent=4)
        save_file(
            f"{book_normalized}.json",
            book_json_content,
            relative_path=str(book_dir.relative_to(project_root)),
        )
        logger.info(f"Saved book JSON at {book_json_path}")

    return illustrations
