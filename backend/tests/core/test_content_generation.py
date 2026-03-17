import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.core.content_generation import (
    generate_book,
    build_story_prompt,
    validate_book_for_prompt_path,
    initialize_illustration_style_sequence,
    _next_illustration_style,
)
from src.core import content_generation
from src.core.prompts import prompts as pt
from src.api.models.book_models import Book


@pytest.mark.asyncio
@patch("src.core.content_generation.generate_page_illustrations")
@patch("src.core.content_generation.build_text_generator")
async def test_generate_book(
    mock_build_text_generator, mock_generate_page_illustrations, monkeypatch, caplog
):
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
    selected_style = next(
        style
        for style in pt.ILLUSTRATION_STYLE_ATTRIBUTES
        if style["style_id"] == "bold_cartoon_watercolor"
    )
    monkeypatch.setattr(content_generation, "_STYLE_SEQUENCE", [selected_style])
    monkeypatch.setattr(content_generation, "_STYLE_INDEX", 0)

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
    assert book.illustration_style["style_id"] == "bold_cartoon_watercolor"

    # Ensure the text + image generation functions were called
    mock_generator.generate_book_response.assert_awaited_once()
    mock_generate_page_illustrations.assert_called_once()
    assert "Selected illustration style for generation run:" in caplog.text


def test_build_story_prompt_selects_v2():
    prompt = build_story_prompt("A rainy day adventure", "v2")
    assert "Write a children's picture book in JSON." in prompt
    assert '"settings"' in prompt
    assert '"setting_id"' in prompt


def test_initialize_illustration_style_sequence_shuffles_from_source_order(monkeypatch):
    source_style_ids = [style["style_id"] for style in pt.ILLUSTRATION_STYLE_ATTRIBUTES]

    def reverse_in_place(sequence):
        sequence[:] = list(reversed(sequence))

    monkeypatch.setattr(content_generation.random, "shuffle", reverse_in_place)
    monkeypatch.setattr(content_generation, "_STYLE_SEQUENCE", [])
    monkeypatch.setattr(content_generation, "_STYLE_INDEX", 0)

    initialize_illustration_style_sequence()

    shuffled_ids = [
        style["style_id"] for style in content_generation._STYLE_SEQUENCE
    ]
    assert shuffled_ids == list(reversed(source_style_ids))
    assert shuffled_ids != source_style_ids
    assert content_generation._STYLE_INDEX == 0


def test_next_illustration_style_walks_sequence_and_wraps(monkeypatch):
    styles = list(pt.ILLUSTRATION_STYLE_ATTRIBUTES[:3])
    monkeypatch.setattr(content_generation, "_STYLE_SEQUENCE", styles)
    monkeypatch.setattr(content_generation, "_STYLE_INDEX", 0)

    first_style, first_position = _next_illustration_style()
    second_style, second_position = _next_illustration_style()
    third_style, third_position = _next_illustration_style()
    wrapped_style, wrapped_position = _next_illustration_style()

    assert first_style["style_id"] == styles[0]["style_id"]
    assert second_style["style_id"] == styles[1]["style_id"]
    assert third_style["style_id"] == styles[2]["style_id"]
    assert wrapped_style["style_id"] == styles[0]["style_id"]
    assert (first_position, second_position, third_position, wrapped_position) == (
        0,
        1,
        2,
        0,
    )


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
