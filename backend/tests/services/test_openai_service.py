import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.services.openai_service import generate_image, get_book_response
import openai


@pytest.mark.asyncio
@patch("openai.images.generate")
async def test_generate_image_success(mock_generate):
    # Mock successful response
    mock_generate.return_value = MagicMock(
        data=[{"url": "http://example.com/image.png"}]
    )
    prompt = "An illustration of a test"

    response = await generate_image(prompt)

    # Assertions
    mock_generate.assert_called_once_with(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024",
        response_format="b64_json",
    )
    assert response.data[0]["url"] == "http://example.com/image.png"


@pytest.mark.asyncio
@patch("openai.images.generate")
async def test_generate_image_retry_success(mock_generate):
    # Mock exceptions for first two calls, then success
    mock_generate.side_effect = [
        openai.APIConnectionError("Connection error"),
        openai.APITimeoutError("Timeout"),
        MagicMock(data=[{"url": "http://example.com/image.png"}]),
    ]
    prompt = "An illustration of a test"

    response = await generate_image(prompt)

    # Assertions
    assert mock_generate.call_count == 3
    assert response.data[0]["url"] == "http://example.com/image.png"


@pytest.mark.asyncio
@patch("openai.images.generate")
async def test_generate_image_retry_failure(mock_generate):
    # Mock exceptions for all retries
    mock_generate.side_effect = openai.APIConnectionError("Connection error")

    prompt = "An illustration of a test"

    with pytest.raises(Exception):
        await generate_image(prompt)

    # Assertions
    assert mock_generate.call_count == 3  # Max retries


@pytest.mark.asyncio
@patch("openai.chat.completions.create")
async def test_get_book_response_success(mock_create):
    mock_create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"book_title": "Test"}'))]
    )
    prompt = "Write a book about testing"

    response = await get_book_response(prompt)

    # Assertions
    mock_create.assert_called_once()
    assert response == '{"book_title": "Test"}'


@pytest.mark.asyncio
@patch("src.services.openai_service.asyncio.to_thread", new_callable=AsyncMock)
async def test_get_book_response_uses_to_thread(mock_to_thread):
    mock_to_thread.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"book_title":"Threaded"}'))]
    )

    response = await get_book_response("Prompt")

    assert response == '{"book_title":"Threaded"}'
    assert mock_to_thread.await_count == 1


@pytest.mark.asyncio
@patch("src.services.openai_service.asyncio.to_thread", new_callable=AsyncMock)
async def test_generate_image_uses_to_thread(mock_to_thread):
    mock_to_thread.return_value = MagicMock(data=[{"url": "http://example.com/image.png"}])

    response = await generate_image("draw")

    assert response.data[0]["url"] == "http://example.com/image.png"
    assert mock_to_thread.await_count == 1
