from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from core.generation_errors import (
    BookGenerationTimeoutError,
    StoryGenerationTimeoutError,
)
from src.main import app


def _test_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
@patch("src.api.routers.books.content_generation.generate_book")
async def test_create_book_story_timeout_returns_504(mock_generate_book):
    mock_generate_book.side_effect = StoryGenerationTimeoutError(
        timeout_seconds=60,
        stage="generating_story",
        provider="openai",
        model="gpt-5",
        elapsed_seconds=60.0,
    )

    async with _test_client() as client:
        response = await client.post("/books/", json={"theme": "Testing Adventures"})

    assert response.status_code == 504
    assert response.json()["detail"] == "Story generation timed out"
    assert "request_id" in response.json()


@pytest.mark.asyncio
@patch("src.api.routers.books.content_generation.generate_book")
async def test_create_book_total_timeout_returns_504(mock_generate_book):
    mock_generate_book.side_effect = BookGenerationTimeoutError(
        timeout_seconds=300,
        stage="generating_illustrations",
        provider="openai",
        model="gpt-image-1.5",
        elapsed_seconds=300.0,
    )

    async with _test_client() as client:
        response = await client.post("/books/", json={"theme": "Testing Adventures"})

    assert response.status_code == 504
    assert response.json()["detail"] == "Book generation timed out"
    assert "request_id" in response.json()


@pytest.mark.asyncio
@patch("src.api.routers.books.content_generation.generate_book")
async def test_create_book_non_timeout_failure_preserves_current_behavior(
    mock_generate_book,
):
    mock_generate_book.side_effect = ValueError("not content policy")

    async with _test_client() as client:
        response = await client.post("/books/", json={"theme": "Testing Adventures"})

    assert response.status_code == 500
    assert "request_id=" in response.json()["detail"]
