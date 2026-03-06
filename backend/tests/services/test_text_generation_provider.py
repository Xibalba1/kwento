from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.services.text_generation_provider import (
    GoogleTextGenerator,
    OpenAITextGenerator,
    build_text_generator,
)


@pytest.mark.asyncio
@patch(
    "src.services.text_generation_provider.openai_service.get_book_response",
    new_callable=AsyncMock,
)
async def test_openai_text_generator_is_mockable(mock_get_book_response):
    mock_get_book_response.return_value = '{"book_title":"Test"}'
    generator = OpenAITextGenerator(model="gpt-5-mini")

    response = await generator.generate_book_response("write a book")

    assert response == '{"book_title":"Test"}'
    mock_get_book_response.assert_awaited_once_with(
        prompt_content="write a book",
        model="gpt-5-mini",
    )


@pytest.mark.asyncio
async def test_google_text_generator_is_mockable_without_network():
    fake_response = SimpleNamespace(text='{"book_title":"From Gemini"}')
    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda model, contents, config: fake_response
        )
    )

    with patch.object(GoogleTextGenerator, "_build_client", return_value=fake_client):
        generator = GoogleTextGenerator(model="gemini-2.5-flash")

    response = await generator.generate_book_response("write a book")
    assert response == '{"book_title":"From Gemini"}'


def test_build_text_generator_routes_from_config(monkeypatch):
    monkeypatch.setattr(
        "src.services.text_generation_provider.settings.text_provider",
        "openai",
    )

    generator = build_text_generator()
    assert isinstance(generator, OpenAITextGenerator)
