import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.core.content_generation import (
    generate_book,
    build_story_prompt,
    validate_book_for_prompt_path,
)
from src.api.models.book_models import Book


@pytest.mark.asyncio
@patch("src.core.content_generation.generate_page_illustrations")
@patch("src.core.content_generation.build_text_generator")
async def test_generate_book(mock_build_text_generator, mock_generate_page_illustrations):
    # Mock OpenAI's response for get_book_response
    assistant_message = """
    {
        "book_title": "The Adventures of Testy McTestface",
        "book_length_n_pages": 2,
        "characters": [
            {
                "name": "Testy McTestface",
                "description": "A curious explorer",
                "appearance": "Tall with a big hat"
            }
        ],
        "settings": [
            {
                "id": "S1",
                "name": "Path Start",
                "visual_anchor_details": "Morning light, pebble path, green bushes"
            },
            {
                "id": "S2",
                "name": "Treasure Cave",
                "visual_anchor_details": "Warm glow, wooden chest, stone walls"
            }
        ],
        "plot_synopsis": "An exciting journey into the world of testing.",
        "pages": [
            {
                "page_number": 1,
                "setting_id": "S1",
                "content": {
                    "text_content_of_this_page": "Testy begins his journey.",
                    "illustration": "Testy standing at the start of a path.",
                    "characters_in_this_page": ["Testy McTestface"]
                }
            },
            {
                "page_number": 2,
                "setting_id": "S2",
                "content": {
                    "text_content_of_this_page": "Testy finds a treasure.",
                    "illustration": "Testy holding a treasure chest.",
                    "characters_in_this_page": ["Testy McTestface"]
                }
            }
        ]
    }
    """
    mock_generator = MagicMock()
    mock_generator.generate_book_response = AsyncMock(return_value=assistant_message)
    mock_build_text_generator.return_value = mock_generator

    # Mock generate_page_illustrations
    mock_generate_page_illustrations.return_value = (
        {
            1: {"saved_path": "book/images/1.png"},
            2: {"saved_path": "book/images/2.png"},
        },
        {
            "saved_path": "book/cover.png",
            "provider": "openai",
            "model": "gpt-image-1.5",
        },
    )

    # Call the function
    theme = "Testing Adventures"
    book = await generate_book(theme)

    # Assertions
    assert isinstance(book, Book)
    assert book.book_title == "The Adventures of Testy McTestface"
    assert len(book.pages) == 2
    assert book.pages[0].page_number == 1
    assert (
        book.pages[0].content.text_content_of_this_page == "Testy begins his journey."
    )
    assert isinstance(book.pages[0].content.illustration, dict)
    assert book.pages[1].page_number == 2
    assert book.pages[1].content.text_content_of_this_page == "Testy finds a treasure."
    assert isinstance(book.pages[1].content.illustration, dict)
    assert isinstance(book.cover, dict)

    # Ensure the text + image generation functions were called
    mock_generator.generate_book_response.assert_awaited_once()
    mock_generate_page_illustrations.assert_called_once()


def test_build_story_prompt_selects_v2():
    prompt = build_story_prompt("A rainy day adventure", "v2")
    assert "Write a children's picture book in JSON." in prompt
    assert '"settings"' in prompt
    assert '"setting_id"' in prompt


def test_build_story_prompt_selects_v3():
    prompt = build_story_prompt("A rainy day adventure", "v3")
    assert "Interesting, adventurous, and fun!" in prompt
    assert '"settings"' in prompt
    assert '"setting_id"' in prompt


def test_validate_book_for_prompt_path_v2_requires_settings():
    book = Book(
        book_title="Test",
        book_length_n_pages=1,
        characters=[
            {
                "name": "A",
                "description": "D",
                "appearance": "P",
            }
        ],
        plot_synopsis="Plot",
        pages=[
            {
                "page_number": 1,
                "content": {
                    "text_content_of_this_page": "Text",
                    "illustration": "Illustration",
                    "characters_in_this_page": ["A"],
                },
            }
        ],
    )
    with pytest.raises(ValueError):
        validate_book_for_prompt_path(book, "v2")
    with pytest.raises(ValueError):
        validate_book_for_prompt_path(book, "v3")
