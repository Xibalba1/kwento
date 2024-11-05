import pytest
from httpx import AsyncClient
from kwento_backend.main import app
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
@patch("kwento_backend.api.routers.books.content_generation.generate_book")
async def test_create_book(mock_generate_book):
    # Mock generate_book
    mock_book = MagicMock()
    mock_book.book_title = "The Adventures of Testy McTestface"
    mock_book.pages = [MagicMock(), MagicMock()]
    mock_book.pages[0].page_number = 1
    mock_book.pages[0].content.text_content_of_this_page = "Testy begins his journey."
    mock_book.pages[0].content.illustration = "http://example.com/image1.png"
    mock_book.pages[0].content.characters_in_this_page = ["Testy McTestface"]
    mock_book.pages[1].page_number = 2
    mock_book.pages[1].content.text_content_of_this_page = "Testy finds a treasure."
    mock_book.pages[1].content.illustration = "http://example.com/image2.png"
    mock_book.pages[1].content.characters_in_this_page = ["Testy McTestface"]
    mock_generate_book.return_value = mock_book

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/books/", json={"theme": "Testing Adventures"})

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "The Adventures of Testy McTestface"
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page_number"] == 1
    assert data["pages"][0]["text_content"] == "Testy begins his journey."
    assert data["pages"][0]["illustration_url"] == "http://example.com/image1.png"

    # Ensure that generate_book was called
    mock_generate_book.assert_called_once_with("Testing Adventures")
