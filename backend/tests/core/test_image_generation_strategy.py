import uuid
import json
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
from src.core.prompts import prompts as pt


class FakeImageGenerator:
    provider = "fake"
    model = "fake-model"

    def __init__(self):
        self.requests = []

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.requests.append(request)
        return ImageGenerationResponse(
            image_bytes=b"image-bytes",
            provider=self.provider,
            model=self.model,
        )


class RetryImageGenerator:
    provider = "fake"
    model = "fake-model"

    def __init__(self, failures_before_success: int):
        self.failures_before_success = failures_before_success
        self.calls = 0
        self.requests = []

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self.calls += 1
        self.requests.append(request)
        if self.calls <= self.failures_before_success:
            raise RuntimeError("transient")
        return ImageGenerationResponse(
            image_bytes=b"ok",
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
        plot_synopsis="A short synopsis",
        settings=[],
        characters=[],
        illustration_style={"style": "storybook"},
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

    _, cover_result = await strategy.generate(book, book_dir="book", images_dir="book/images")

    assert len(fake_generator.requests) == 4
    assert fake_generator.requests[0].reference_images is None
    for request in fake_generator.requests[1:]:
        assert request.reference_images == [b"image-bytes"]

    page_requests = [r for r in fake_generator.requests if r.page_index is not None]
    prompt_one = page_requests[0].prompt
    prompt_two = page_requests[1].prompt
    prompt_three = page_requests[2].prompt

    body_one = json.loads(prompt_one[len(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE) :].strip())
    body_two = json.loads(prompt_two[len(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE) :].strip())
    body_three = json.loads(prompt_three[len(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE) :].strip())

    assert "illustration_style" in body_one
    assert "illustration_style" not in body_two
    assert "illustration_style" not in body_three
    assert "4" not in body_one["SYSTEM_NOTES"]
    assert (
        body_two["SYSTEM_NOTES"]["4"]
        == pt.PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE
    )
    assert (
        body_three["SYSTEM_NOTES"]["4"]
        == pt.PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE
    )
    assert cover_result["saved_path"] == "saved://book/cover.png"


def test_seeded_strategy_worker_count():
    strategy = SeededReferenceEditStrategy(FakeImageGenerator())
    assert strategy._determine_parallel_workers(0) == 0
    assert strategy._determine_parallel_workers(1) == 1
    assert strategy._determine_parallel_workers(2) == 2
    assert strategy._determine_parallel_workers(3) == 3
    assert strategy._determine_parallel_workers(10) == 4


@pytest.mark.asyncio
async def test_seeded_strategy_retries_transient_errors(monkeypatch):
    generator = RetryImageGenerator(failures_before_success=1)
    strategy = SeededReferenceEditStrategy(generator)
    book = _make_book()

    monkeypatch.setattr(
        image_generation.image_service,
        "save_image",
        lambda image_data, relative_filepath: f"saved://{relative_filepath}",
    )
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_retry_attempts",
        3,
    )
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_retry_backoff_base_seconds",
        0.0,
    )
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_retry_backoff_max_seconds",
        0.0,
    )
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_retry_use_jitter",
        False,
    )

    await strategy.generate(book, book_dir="book", images_dir="book/images")
    assert generator.calls >= 5  # at least one retry plus seed+cover+2 pages


@pytest.mark.asyncio
async def test_seeded_strategy_fails_whole_book_after_retries(monkeypatch):
    generator = RetryImageGenerator(failures_before_success=999)
    strategy = SeededReferenceEditStrategy(generator)
    book = _make_book()

    monkeypatch.setattr(
        image_generation.image_service,
        "save_image",
        lambda image_data, relative_filepath: f"saved://{relative_filepath}",
    )
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_retry_attempts",
        3,
    )
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_retry_backoff_base_seconds",
        0.0,
    )
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_retry_backoff_max_seconds",
        0.0,
    )
    monkeypatch.setattr(
        image_generation.settings,
        "image_generation_retry_use_jitter",
        False,
    )

    with pytest.raises(image_generation.ImageGenerationPipelineError):
        await strategy.generate(book, book_dir="book", images_dir="book/images")
