import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from src.services.image_generation_provider import (
    GoogleImageGenerator,
    ImageGenerationRequest,
    OpenAIImageGenerator,
)


@pytest.mark.asyncio
@patch("src.services.image_generation_provider.openai_service.generate_image", new_callable=AsyncMock)
async def test_openai_image_generator_is_mockable(mock_generate_image):
    raw_bytes = b"fake-image-bytes"
    mock_generate_image.return_value = SimpleNamespace(
        data=[SimpleNamespace(b64_json=base64.b64encode(raw_bytes).decode("utf-8"))]
    )
    generator = OpenAIImageGenerator(model="dall-e-3")

    response = await generator.generate(ImageGenerationRequest(prompt="draw a cat"))

    assert response.image_bytes == raw_bytes
    mock_generate_image.assert_awaited_once()


@pytest.mark.asyncio
@patch(
    "src.services.image_generation_provider.openai_service.generate_image_with_reference",
    new_callable=AsyncMock,
)
async def test_openai_image_generator_uses_reference_edit_when_seeded(
    mock_generate_image_with_reference,
):
    raw_bytes = b"fake-image-bytes"
    mock_generate_image_with_reference.return_value = SimpleNamespace(
        data=[SimpleNamespace(b64_json=base64.b64encode(raw_bytes).decode("utf-8"))]
    )
    generator = OpenAIImageGenerator(model="gpt-image-1.5")

    response = await generator.generate(
        ImageGenerationRequest(prompt="draw a cat", reference_images=[b"seed"])
    )

    assert response.image_bytes == raw_bytes
    mock_generate_image_with_reference.assert_awaited_once_with(
        "draw a cat",
        reference_images=[b"seed"],
        model="gpt-image-1.5",
    )


@pytest.mark.asyncio
async def test_google_image_generator_is_mockable_without_network():
    fake_part = SimpleNamespace(inline_data=SimpleNamespace(data=b"google-image-bytes"))
    fake_response = SimpleNamespace(parts=[fake_part])
    fake_client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda model, contents, config: fake_response
        )
    )

    seed_img = Image.new("RGB", (1, 1), color="white")
    seed_buffer = io.BytesIO()
    seed_img.save(seed_buffer, format="PNG")
    seed_bytes = seed_buffer.getvalue()

    with patch.object(GoogleImageGenerator, "_build_client", return_value=fake_client):
        generator = GoogleImageGenerator(model="gemini-image")

    response = await generator.generate(
        ImageGenerationRequest(prompt="draw a fox", reference_images=[seed_bytes])
    )

    assert response.image_bytes == b"google-image-bytes"
