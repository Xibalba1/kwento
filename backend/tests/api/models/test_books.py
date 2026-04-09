import pytest
from httpx import AsyncClient
from src.main import app
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
@patch("src.api.routers.books.content_generation.generate_book")
async def test_create_book(mock_generate_book):
    # Mock generate_book
    mock_book = MagicMock()
    mock_book.book_title = "The Adventures of Testy McTestface"
    mock_book.book_id = "test-book-id"
    mock_book.cover = {
        "url": "http://example.com/cover.png",
        "expires_at": "2026-01-01T00:00:00Z",
    }
    mock_book.pages = [MagicMock(), MagicMock()]
    mock_book.pages[0].page_number = 1
    mock_book.pages[0].content.text_content_of_this_page = "Testy begins his journey."
    mock_book.pages[0].content.illustration = {
        "url": "http://example.com/image1.png",
        "expires_at": "2026-01-01T00:00:00Z",
    }
    mock_book.pages[0].content.characters_in_this_page = ["Testy McTestface"]
    mock_book.pages[1].page_number = 2
    mock_book.pages[1].content.text_content_of_this_page = "Testy finds a treasure."
    mock_book.pages[1].content.illustration = {
        "url": "http://example.com/image2.png",
        "expires_at": "2026-01-01T00:00:00Z",
    }
    mock_book.pages[1].content.characters_in_this_page = ["Testy McTestface"]
    mock_generate_book.return_value = mock_book

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/books/", json={"theme": "Testing Adventures"})

    # Assertions
    assert response.status_code == 200
    data = response.json()
    assert data["book_title"] == "The Adventures of Testy McTestface"
    assert "created_at" in data
    assert len(data["images"]) == 2
    assert data["images"][0]["page"] == 1
    assert data["images"][0]["url"] == "http://example.com/image1.png"
    assert data["cover"]["url"] == "http://example.com/cover.png"

    # Ensure that generate_book was called
    args, kwargs = mock_generate_book.call_args
    assert args[0] == "Testing Adventures"
    assert "request_id" in kwargs
