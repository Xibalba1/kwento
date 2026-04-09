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
@patch("src.api.routers.books.get_book_list")
async def test_list_books_includes_created_at(mock_get_book_list):
    mock_get_book_list.return_value = [
        {
            "book_id": "book-list-1",
            "book_title": "List Book",
            "created_at": "2026-04-02T00:00:00Z",
            "json_url": "https://example.com/book-list-1.json",
            "expires_at": "2026-04-02T00:00:00Z",
            "cover": None,
            "images": [],
            "is_archived": False,
            "is_favorite": False,
        }
    ]

    async with _test_client() as client:
        response = await client.get("/books/")

    assert response.status_code == 200
    assert response.json()[0]["created_at"] == "2026-04-02T00:00:00Z"


@pytest.mark.asyncio
@patch("src.api.routers.books.get_book_by_id")
async def test_fetch_book_by_id_includes_created_at(mock_get_book_by_id):
    mock_get_book_by_id.return_value = {
        "book_id": "book-detail-1",
        "book_title": "Detail Book",
        "created_at": "2026-04-02T00:00:00Z",
        "json_url": "https://example.com/book-detail-1.json",
        "expires_at": "2026-04-02T00:00:00Z",
        "cover": None,
        "images": [],
        "is_archived": False,
        "is_favorite": False,
    }

    async with _test_client() as client:
        response = await client.get("/books/book-detail-1/")

    assert response.status_code == 200
    assert response.json()["created_at"] == "2026-04-02T00:00:00Z"


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


@pytest.mark.asyncio
@patch("src.api.routers.books.get_book_by_id")
@patch("src.api.routers.books.save_book_library_state")
async def test_patch_library_state_updates_archive_state(
    mock_save_book_library_state,
    mock_get_book_by_id,
):
    mock_get_book_by_id.side_effect = [
        {
            "book_id": "book-1",
            "book_title": "Archive Book",
            "created_at": "2026-04-02T00:00:00Z",
            "json_url": "https://example.com/book-1.json",
            "expires_at": "2026-04-02T00:00:00Z",
            "cover": None,
            "images": [],
            "is_archived": False,
            "is_favorite": False,
        },
        {
            "book_id": "book-1",
            "book_title": "Archive Book",
            "created_at": "2026-04-02T00:00:00Z",
            "json_url": "https://example.com/book-1.json",
            "expires_at": "2026-04-02T00:00:00Z",
            "cover": None,
            "images": [],
            "is_archived": True,
            "is_favorite": False,
        },
    ]

    async with _test_client() as client:
        response = await client.patch("/books/book-1/library-state/", json={"is_archived": True})

    assert response.status_code == 200
    assert response.json()["is_archived"] is True
    assert response.json()["created_at"] == "2026-04-02T00:00:00Z"
    mock_save_book_library_state.assert_called_once_with("book-1", is_archived=True, is_favorite=None)


@pytest.mark.asyncio
@patch("src.api.routers.books.get_book_by_id")
async def test_patch_library_state_returns_404_for_missing_book(mock_get_book_by_id):
    mock_get_book_by_id.side_effect = ValueError("missing")

    async with _test_client() as client:
        response = await client.patch("/books/missing/library-state/", json={"is_archived": True})

    assert response.status_code == 404
    assert response.json()["detail"] == "Book not found."


@pytest.mark.asyncio
@patch("src.api.routers.books.get_book_by_id")
@patch("src.api.routers.books.save_book_library_state")
async def test_patch_library_state_updates_favorite_state(
    mock_save_book_library_state,
    mock_get_book_by_id,
):
    mock_get_book_by_id.side_effect = [
        {
            "book_id": "book-2",
            "book_title": "Favorite Book",
            "created_at": "2026-04-02T00:00:00Z",
            "json_url": "https://example.com/book-2.json",
            "expires_at": "2026-04-02T00:00:00Z",
            "cover": None,
            "images": [],
            "is_archived": False,
            "is_favorite": False,
        },
        {
            "book_id": "book-2",
            "book_title": "Favorite Book",
            "created_at": "2026-04-02T00:00:00Z",
            "json_url": "https://example.com/book-2.json",
            "expires_at": "2026-04-02T00:00:00Z",
            "cover": None,
            "images": [],
            "is_archived": False,
            "is_favorite": True,
        },
    ]

    async with _test_client() as client:
        response = await client.patch("/books/book-2/library-state/", json={"is_favorite": True})

    assert response.status_code == 200
    assert response.json()["is_favorite"] is True
    assert response.json()["created_at"] == "2026-04-02T00:00:00Z"
    mock_save_book_library_state.assert_called_once_with("book-2", is_archived=None, is_favorite=True)


@pytest.mark.asyncio
@patch("src.api.routers.books.get_book_by_id")
@patch("src.api.routers.books.save_book_library_state")
async def test_patch_library_state_restores_archived_favorite_book(
    mock_save_book_library_state,
    mock_get_book_by_id,
):
    mock_get_book_by_id.side_effect = [
        {
            "book_id": "book-3",
            "book_title": "Archived Favorite Book",
            "created_at": "2026-04-02T00:00:00Z",
            "json_url": "https://example.com/book-3.json",
            "expires_at": "2026-04-02T00:00:00Z",
            "cover": None,
            "images": [],
            "is_archived": True,
            "is_favorite": False,
        },
        {
            "book_id": "book-3",
            "book_title": "Archived Favorite Book",
            "created_at": "2026-04-02T00:00:00Z",
            "json_url": "https://example.com/book-3.json",
            "expires_at": "2026-04-02T00:00:00Z",
            "cover": None,
            "images": [],
            "is_archived": False,
            "is_favorite": True,
        },
    ]

    async with _test_client() as client:
        response = await client.patch("/books/book-3/library-state/", json={"is_favorite": True})

    assert response.status_code == 200
    assert response.json()["is_archived"] is False
    assert response.json()["is_favorite"] is True
    assert response.json()["created_at"] == "2026-04-02T00:00:00Z"
    mock_save_book_library_state.assert_called_once_with("book-3", is_archived=None, is_favorite=True)
