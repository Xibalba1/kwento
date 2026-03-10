"""
test_image_generation.py
========================

This module contains unit tests for the `image_generation` functions in the `src.core` package. The tests focus on verifying the functionality and robustness of the `make_illustration_prompt` and `generate_single_page_illustration` functions, ensuring they handle various input scenarios and errors correctly.

Usage
-----

To run the tests in this module, use the following command:

```bash
pytest backend/tests/core/test_image_generation.py
"""

import pytest
from unittest.mock import MagicMock, patch
from src.api.models.book_models import Page, Character
from src.core.image_generation import make_illustration_prompt
import json
from src.core.image_generation import generate_single_page_illustration
from src.core.prompts import prompts as pt
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Helper function to dynamically create Page mocks with Character objects
def create_mock_page(
    illustration_style, illustration, text_content, characters, page_number=1
):
    class MockContent:
        def __init__(self, illustration, text_content, characters):
            self.illustration = illustration
            self.text_content_of_this_page = text_content
            # Convert list of dicts to list of Character objects
            self.characters_in_this_page_data = [
                Character(**char_dict) for char_dict in characters
            ]

    class MockBookParent:
        def __init__(self, illustration_style):
            self.illustration_style = illustration_style

    page = MagicMock(spec=Page)
    page.page_number = page_number
    page.book_parent = MockBookParent(illustration_style)
    page.content = MockContent(illustration, text_content, characters)
    return page


@pytest.mark.parametrize(
    "illustration_style, illustration, text_content, characters",
    [
        (
            "fantasy",
            "A magical forest",
            "Once upon a time...",
            [
                {
                    "name": "Elf",
                    "appearance": "Small and nimble",
                    "description": "A short elf with big ears wearing a green tunic and wearing golden shoes.",
                }
            ],
        ),
        (
            "sci-fi",
            "A futuristic city",
            "In a distant galaxy...",
            [
                {
                    "name": "Robot",
                    "appearance": "Metallic",
                    "description": "A 10 foot tall robot of glistening steel. The robot is in the style of how robots were imagined in 1950s sci-fi",
                }
            ],
        ),
        (
            "historical",
            "An ancient battle scene",
            "Long ago in a forgotten era...",
            [
                {
                    "name": "Knight",
                    "appearance": "Armored and brave",
                    "description": "A knight in shinging armor. Tall and carries a lance.",
                }
            ],
        ),
    ],
)
def test_make_illustration_prompt(
    illustration_style, illustration, text_content, characters
):
    mock_page = create_mock_page(
        illustration_style, illustration, text_content, characters
    )

    # Generate the prompt and parse the JSON body
    prompt = make_illustration_prompt(mock_page)
    prompt_json = json.loads(prompt[len(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE) :].strip())

    # Assertions on structure and dynamic content
    assert prompt_json["illustration_style"] == illustration_style
    assert prompt_json["illustration_description"] == illustration
    assert prompt_json["text_content"] == text_content
    assert isinstance(prompt_json["characters_in_illustration"], list)
    assert len(prompt_json["characters_in_illustration"]) == len(characters)

    # Check character details in prompt
    for character, char_data in zip(
        prompt_json["characters_in_illustration"], characters
    ):
        assert character["name"] == char_data["name"]
        assert character["appearance"] == char_data["appearance"]


def test_make_illustration_prompt_missing_book_parent():
    """
    Test make_illustration_prompt when page.book_parent is None.
    Expect an AttributeError because illustration_style cannot be accessed.
    """
    mock_page = create_mock_page(
        illustration_style=None,
        illustration="A magical forest",
        text_content="Once upon a time...",
        characters=[
            {
                "name": "Elf",
                "appearance": "Small and nimble",
                "description": "A short elf with big ears wearing a green tunic and wearing golden shoes.",
            }
        ],
    )
    mock_page.book_parent = None  # Remove book_parent

    with pytest.raises(AttributeError):
        make_illustration_prompt(mock_page)


def test_make_illustration_prompt_missing_content():
    """
    Test make_illustration_prompt when page.content is None.
    Expect an AttributeError because content attributes cannot be accessed.
    """
    mock_page = MagicMock(spec=Page)
    mock_page.page_number = 1
    mock_page.book_parent = MagicMock()
    mock_page.book_parent.illustration_style = "fantasy"
    mock_page.content = None  # Remove content

    with pytest.raises(AttributeError):
        make_illustration_prompt(mock_page)


def test_make_illustration_prompt_empty_characters():
    """
    Test make_illustration_prompt when characters_in_this_page_data is empty.
    Expect the prompt to include an empty list for characters_in_illustration.
    """
    mock_page = create_mock_page(
        illustration_style="fantasy",
        illustration="A magical forest",
        text_content="Once upon a time...",
        characters=[],
    )

    # Generate the prompt and parse the JSON body
    prompt = make_illustration_prompt(mock_page)
    prompt_json = json.loads(prompt[len(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE) :].strip())

    assert prompt_json["characters_in_illustration"] == []


@pytest.mark.parametrize("prompt_version", ["v2", "v3"])
def test_make_illustration_prompt_v2_v3_injects_setting_anchor_values(
    monkeypatch, prompt_version
):
    mock_page = create_mock_page(
        illustration_style="fantasy",
        illustration="A magical forest",
        text_content="Once upon a time...",
        characters=[
            {
                "name": "Elf",
                "appearance": "Small and nimble",
                "description": "A short elf with big ears wearing a green tunic and wearing golden shoes.",
            }
        ],
    )
    mock_page.setting_id = "S1"
    mock_page.book_parent.settings = [
        MagicMock(
            id="S1",
            name="Forest Clearing",
            visual_anchor_details="Dappled sunlight, mossy stones, tall pines",
        )
    ]
    monkeypatch.setattr(
        "src.core.image_generation.settings.prompt_path_version",
        prompt_version,
    )

    prompt = make_illustration_prompt(mock_page, include_style=False)
    prompt_json = json.loads(prompt[len(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE) :].strip())

    assert "illustration_style" not in prompt_json
    assert prompt_json["setting_name"] == "Forest Clearing"
    assert (
        prompt_json["setting_visual_anchor_details"]
        == "Dappled sunlight, mossy stones, tall pines"
    )
    assert "setting_id" not in prompt_json


@pytest.mark.asyncio
@patch("src.services.openai_service.generate_image")
async def test_generate_single_page_illustration(mock_generate_image):
    # Mock response
    mock_generate_image.return_value = MagicMock(
        data=[{"url": "http://example.com/image.png"}]
    )

    # Use helper function to create a dynamic page mock
    mock_page = create_mock_page(
        illustration_style="fantasy",
        illustration="A magical forest",
        text_content="Once upon a time...",
        characters=[
            {
                "name": "Robot",
                "appearance": "Metallic",
                "description": "A 10 foot tall robot of glistening steel. The robot is in the style of how robots were imagined in 1950s sci-fi",
            }
        ],
    )

    # Generate illustration
    illustration_prompt = make_illustration_prompt(mock_page)
    result = await generate_single_page_illustration(mock_page, illustration_prompt)

    # Assertions
    mock_generate_image.assert_called_once_with(illustration_prompt)
    assert result["url"] == "http://example.com/image.png"


@pytest.mark.asyncio
@patch("src.services.openai_service.generate_image")
async def test_generate_single_page_illustration_api_error(mock_generate_image):
    """
    Test generate_single_page_illustration when the OpenAI API raises an exception.
    Expect the function to raise the exception.
    """
    # Mock generate_image to raise an exception
    mock_generate_image.side_effect = Exception("API error")

    # Use helper function to create a dynamic page mock
    mock_page = create_mock_page(
        illustration_style="fantasy",
        illustration="A magical forest",
        text_content="Once upon a time...",
        characters=[
            {
                "name": "Robot",
                "appearance": "Metallic",
                "description": "A 10 foot tall robot of glistening steel. The robot is in the style of how robots were imagined in 1950s sci-fi",
            }
        ],
    )

    # Generate illustration prompt
    illustration_prompt = make_illustration_prompt(mock_page)

    with pytest.raises(Exception) as exc_info:
        await generate_single_page_illustration(mock_page, illustration_prompt)

    assert str(exc_info.value) == "API error"


@pytest.mark.asyncio
@patch("src.services.openai_service.generate_image")
async def test_generate_single_page_illustration_invalid_response(mock_generate_image):
    """
    Test generate_single_page_illustration when OpenAI API returns an invalid response.
    Expect an IndexError when accessing response data.
    """
    # Mock generate_image to return invalid data
    mock_generate_image.return_value = MagicMock(data=[])

    # Use helper function to create a dynamic page mock
    mock_page = create_mock_page(
        illustration_style="fantasy",
        illustration="A magical forest",
        text_content="Once upon a time...",
        characters=[
            {
                "name": "Robot",
                "appearance": "Metallic",
                "description": "A 10 foot tall robot of glistening steel. The robot is in the style of how robots were imagined in 1950s sci-fi",
            }
        ],
    )

    # Generate illustration prompt
    illustration_prompt = make_illustration_prompt(mock_page)

    with pytest.raises(IndexError):
        await generate_single_page_illustration(mock_page, illustration_prompt)
