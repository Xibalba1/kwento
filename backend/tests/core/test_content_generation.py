import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.core.content_generation import generate_book
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
        "plot_synopsis": "An exciting journey into the world of testing.",
        "pages": [
            {
                "page_number": 1,
                "content": {
                    "text_content_of_this_page": "Testy begins his journey.",
                    "illustration": "Testy standing at the start of a path.",
                    "characters_in_this_page": ["Testy McTestface"]
                }
            },
            {
                "page_number": 2,
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
    mock_generate_page_illustrations.return_value = {
        1: {"url": "http://example.com/image1.png"},
        2: {"url": "http://example.com/image2.png"},
    }

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
    assert book.pages[0].content.illustration == "http://example.com/image1.png"
    assert book.pages[1].page_number == 2
    assert book.pages[1].content.text_content_of_this_page == "Testy finds a treasure."
    assert book.pages[1].content.illustration == "http://example.com/image2.png"

    # Ensure the text + image generation functions were called
    mock_generator.generate_book_response.assert_awaited_once()
    mock_generate_page_illustrations.assert_called_once()
