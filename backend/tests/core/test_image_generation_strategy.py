import uuid
from types import SimpleNamespace

import pytest

from src.core import image_generation
from src.core.image_generation import (
    LegacyIllustrationStrategy,
    SeededReferenceEditStrategy,
    get_illustration_strategy,
)
from src.services.image_generation_provider import (
    ImageGenerationRequest,
    ImageGenerationResponse,
)


class FakeImageGenerator:
    provider = "fake"
    model = "fake-model"

    def __init__(self):
        self.requests = []
        self.responses = [b"seed-bytes", b"page-2-bytes", b"page-3-bytes"]

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.requests.append(request)
        image_bytes = self.responses[len(self.requests) - 1]
        return ImageGenerationResponse(
            image_bytes=image_bytes,
            provider=self.provider,
            model=self.model,
        )


def _make_page(page_number: int, illustration_text: str):
    content = SimpleNamespace(
        illustration=illustration_text,
        text_content_of_this_page=f"Page {page_number} text",
        characters_in_this_page_data=[],
        illustration_prompt=None,
    )
    book_parent = SimpleNamespace(illustration_style={"style": "storybook"})
    return SimpleNamespace(page_number=page_number, content=content, book_parent=book_parent)


def _make_book():
    return SimpleNamespace(
        book_id=uuid.uuid4(),
        book_title="Test Book",
        pages=[
            _make_page(1, "Scene 1"),
            _make_page(2, "Scene 2"),
            _make_page(3, "Scene 3"),
        ],
    )


def test_get_illustration_strategy_routes_from_config(monkeypatch):
    fake_generator = FakeImageGenerator()
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_strategy",
        "seeded_reference_edit",
    )
    monkeypatch.setattr(
        image_generation,
        "build_image_generator",
        lambda provider=None: fake_generator,
    )

    strategy = get_illustration_strategy()
    assert isinstance(strategy, SeededReferenceEditStrategy)


def test_get_illustration_strategy_routes_legacy():
    strategy = get_illustration_strategy(
        strategy_name="legacy",
        image_generator=FakeImageGenerator(),
    )
    assert isinstance(strategy, LegacyIllustrationStrategy)


@pytest.mark.asyncio
async def test_seeded_strategy_uses_seed_reference_for_subsequent_pages(monkeypatch):
    fake_generator = FakeImageGenerator()
    strategy = SeededReferenceEditStrategy(fake_generator)
    book = _make_book()

    monkeypatch.setattr(
        image_generation.image_service,
        "save_image",
        lambda image_data, relative_filepath: f"saved://{relative_filepath}",
    )

    await strategy.generate(book, images_dir="book/images")

    assert len(fake_generator.requests) == 3
    assert fake_generator.requests[0].reference_images is None
    assert fake_generator.requests[1].reference_images == [b"seed-bytes"]
    assert fake_generator.requests[2].reference_images == [b"seed-bytes"]
