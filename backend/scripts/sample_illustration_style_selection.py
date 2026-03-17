#!/usr/bin/env python3

import argparse
import asyncio
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api.models.book_models import Book
from api.models.helpers import assign_book_model_relationships
from config import settings
from core.content_generation import (
    _to_text_generation_result,
    build_story_prompt,
    validate_book_for_prompt_path,
)
from core.prompts import prompts as pt
from services.text_generation_provider import build_text_generator


async def _select_style_for_theme(theme: str) -> dict:
    prompt_path_version = settings.prompt_path_version
    prompt_content = build_story_prompt(theme, prompt_path_version)

    text_generator = build_text_generator()
    metadata_method = getattr(text_generator, "generate_book_response_with_metadata", None)
    if asyncio.iscoroutinefunction(metadata_method):
        text_result_raw = await metadata_method(prompt_content)
    else:
        text_result_raw = await text_generator.generate_book_response(prompt_content)

    text_result = _to_text_generation_result(
        text_result_raw,
        provider=settings.text_provider,
        model={
            "openai": settings.openai_text_model,
            "google": settings.google_text_model,
        }.get(settings.text_provider, ""),
    )

    book_data = json.loads(text_result.content)
    book = Book(**book_data)
    validate_book_for_prompt_path(book, prompt_path_version)
    assign_book_model_relationships(book)

    # Mirror production behavior exactly: select a style via the process-global RNG.
    import random

    style_attributes = random.choice(pt.ILLUSTRATION_STYLE_ATTRIBUTES)
    book.illustration_style = style_attributes

    return {
        "theme": theme,
        "book_id": str(book.book_id),
        "book_title": book.book_title,
        "prompt_path_version": prompt_path_version,
        "text_provider": text_result.provider,
        "text_model": text_result.model,
        "style_id": style_attributes.get("style_id"),
        "style_display_name": style_attributes.get("style_display_name"),
        "illustration_style": style_attributes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run story generation through illustration-style selection, then exit "
            "without generating any images."
        )
    )
    parser.add_argument("theme", help="Theme to use for story generation.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the resulting JSON payload.",
    )
    args = parser.parse_args()

    result = asyncio.run(_select_style_for_theme(args.theme))
    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
