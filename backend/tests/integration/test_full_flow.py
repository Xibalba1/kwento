import pytest
from src.main import app
from httpx import AsyncClient
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
@patch("src.services.openai_service.get_book_response")
@patch("src.services.openai_service.generate_image")
async def test_full_flow(mock_generate_image, mock_get_book_response):
    # Mock OpenAI's response for get_book_response
    assistant_message = """
    {
        "book_title": "The Adventures of Full Flow",
        "book_length_n_pages": 1,
        "characters": [
            {
                "name": "Flow Tester",
                "description": "A character to test full flow",
                "appearance": "Average height with a testing hat"
            }
        ],
        "settings": [
            {
                "id": "S1",
                "name": "Desk Corner",
                "visual_anchor_details": "Desk lamp glow, notebook stack, blue chair"
            }
        ],
        "plot_synopsis": "Testing the full flow of the application.",
        "pages": [
            {
                "page_number": 1,
                "setting_id": "S1",
                "content": {
                    "text_content_of_this_page": "Flow Tester starts testing.",
                    "illustration": "Flow Tester at a desk.",
                    "characters_in_this_page": ["Flow Tester"]
                }
            }
        ]
    }
    """
    mock_get_book_response.return_value = assistant_message

    # Mock OpenAI's response for generate_image
    mock_generate_image.return_value = MagicMock(
        data=[{"url": "http://example.com/image.png"}]
    )

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/books/", json={"theme": "Full Flow Testing"})

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "The Adventures of Full Flow"
    assert len(data["pages"]) == 1
    assert data["pages"][0]["page_number"] == 1
    assert data["pages"][0]["text_content"] == "Flow Tester starts testing."
    assert data["pages"][0]["illustration_url"] == "http://example.com/image.png"
