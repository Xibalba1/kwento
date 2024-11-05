# backend/src/kwento_backend/core/image_generation.py

import json
import logging
from typing import Dict, Any
import base64

from kwento_backend.services import openai_service, image_service
from kwento_backend.api.models.book_models import Page
from kwento_backend.core.prompts import prompts as pt

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
    page: Page, illustration_prompt: str
) -> Dict[str, Any]:
    try:
        page.content.illustration_prompt = illustration_prompt

        response = await openai_service.generate_image(illustration_prompt)
        image_b64 = response.data[0].b64_json

        image_data = base64.b64decode(image_b64)

        filename = f"images/page_{page.page_number}.png"
        saved_path = image_service.save_image_locally(image_data, filename)

        page.content.illustration = saved_path
        page.content.illustration_b64_data = image_b64

        return {"image_data": image_b64}
    except Exception as e:
        logger.error(f"Error generating illustration for page {page.page_number}: {e}")
        raise


async def generate_page_illustrations(book) -> Dict[int, Any]:
    illustrations = {}
    logger.info(f"Generating illustrations for the book '{book.book_title}'")
    for page in book.pages:
        illustration_prompt = make_illustration_prompt(page)
        image_data = await generate_single_page_illustration(page, illustration_prompt)
        illustrations[page.page_number] = image_data
        logger.info(f"Generated illustration for page {page.page_number}")
    return illustrations
