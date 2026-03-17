import uuid
import json
from types import SimpleNamespace

import pytest

from src.core import image_generation
from src.core.image_generation import (
    LegacyIllustrationStrategy,
    SeededReferenceEditStrategy,
    generate_cover_from_reference,
    get_illustration_strategy,
    make_cover_prompt,
    make_illustration_prompt,
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


def _extract_prompt_body(prompt: str) -> dict:
    preface_index = prompt.index(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE)
    body_text = prompt[preface_index + len(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE) :].strip()
    return json.loads(body_text)


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


def _character(name: str, appearance: str = "appearance"):
    return SimpleNamespace(name=name, appearance=appearance)


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

    body_one = _extract_prompt_body(prompt_one)
    body_two = _extract_prompt_body(prompt_two)
    body_three = _extract_prompt_body(prompt_three)

    assert "illustration_style" in body_one
    assert "illustration_style" in body_two
    assert "illustration_style" in body_three
    assert body_one["duplication_rule"].startswith("Depict each listed character exactly once")
    assert body_two["single_moment_rule"].startswith("Render one continuous moment in time")
    assert body_three["motion_without_duplication_rule"].startswith(
        "Show motion through pose"
    )
    assert (
        body_two["SYSTEM_NOTES"]["12"].startswith(
            pt.PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE
        )
    )
    assert (
        body_three["SYSTEM_NOTES"]["12"].startswith(
            pt.PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE
        )
    )
    assert cover_result["saved_path"] == "saved://book/cover.png"


def test_seeded_strategy_worker_count():
    strategy = SeededReferenceEditStrategy(FakeImageGenerator())
    assert strategy._determine_parallel_workers(0) == 0
    assert strategy._determine_parallel_workers(1) == 1
    assert strategy._determine_parallel_workers(2) == 2
    assert strategy._determine_parallel_workers(3) == 3
    assert strategy._determine_parallel_workers(10) == 4


def test_make_illustration_prompt_adds_duplication_controls():
    page = _make_page(1, "June runs toward the kite.")
    page.content.text_content_of_this_page = "June runs fast."
    page.content.characters_in_this_page_data = [
        _character("June", "yellow overalls"),
        _character("Pip", "small brown puppy"),
    ]
    page.book_parent.illustration_style = {
        "style_id": "bold_cartoon_watercolor",
        "style_display_name": "graphic cartoon watercolor",
    }

    body = _extract_prompt_body(make_illustration_prompt(page))

    assert body["characters_in_illustration"] == [
        {"name": "June", "appearance": "yellow overalls", "count": 1},
        {"name": "Pip", "appearance": "small brown puppy", "count": 1},
    ]
    assert body["character_cardinality_summary"] == "June: 1; Pip: 1"
    assert body["allowed_duplicate_characters"] == []
    assert body["duplication_rule"].startswith("Depict each listed character exactly once")
    assert body["single_moment_rule"].startswith("Render one continuous moment in time")
    assert body["motion_without_duplication_rule"].startswith(
        "Show motion through pose"
    )
    assert body["SYSTEM_NOTES"]["7"].startswith("Depict each listed character exactly once")
    assert body["SYSTEM_NOTES"]["8"].startswith("Render one continuous moment in time")
    assert "montage" in body["SYSTEM_NOTES"]["9"]
    assert "allowed number of times" in body["SYSTEM_NOTES"]["11"]


def test_make_illustration_prompt_enables_explicit_duplication_exception():
    page = _make_page(1, "June appears twice in the same image, with two versions of June jumping rope.")
    page.content.text_content_of_this_page = "The same character appears twice."
    page.content.characters_in_this_page_data = [
        _character("June", "yellow overalls"),
    ]

    body = _extract_prompt_body(make_illustration_prompt(page))

    assert body["allowed_duplicate_characters"] == ["June"]
    assert body["characters_in_illustration"] == [
        {"name": "June", "appearance": "yellow overalls", "count": 2}
    ]
    assert body["duplication_rule"] == (
        "Duplication is intentional only for: June. All other listed characters must appear exactly once."
    )


def test_make_illustration_prompt_keeps_exact_once_for_ambiguous_repeat_language():
    page = _make_page(1, "June runs again toward the hill.")
    page.content.text_content_of_this_page = "June tries again."
    page.content.characters_in_this_page_data = [
        _character("June", "yellow overalls"),
    ]

    body = _extract_prompt_body(make_illustration_prompt(page))

    assert body["allowed_duplicate_characters"] == []
    assert body["characters_in_illustration"] == [
        {"name": "June", "appearance": "yellow overalls", "count": 1}
    ]


def test_make_cover_prompt_adds_duplication_controls():
    book = _make_book()
    book.characters = [_character("June", "yellow overalls"), _character("Pip", "brown puppy")]
    book.illustration_style = {
        "style_id": "storybook_gouache",
        "style_display_name": "matte gouache painting",
    }

    body = _extract_prompt_body(make_cover_prompt(book))

    assert body["character_cardinality_summary"] == "June: 1; Pip: 1"
    assert body["allowed_duplicate_characters"] == []
    assert body["characters_in_illustration"] == [
        {"name": "June", "appearance": "yellow overalls", "count": 1},
        {"name": "Pip", "appearance": "brown puppy", "count": 1},
    ]
    assert body["SYSTEM_NOTES"]["12"].startswith("This is a book cover illustration")


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


@pytest.mark.asyncio
async def test_generate_cover_from_reference_uses_cover_prompt_and_reference(monkeypatch):
    fake_generator = FakeImageGenerator()
    book = _make_book()

    monkeypatch.setattr(
        image_generation.image_service,
        "save_image",
        lambda image_data, relative_filepath: f"saved://{relative_filepath}",
    )

    result = await generate_cover_from_reference(
        book,
        b"seed-reference",
        image_generator=fake_generator,
    )

    assert result["saved_path"] == f"saved://{book.book_id}/cover.png"
    assert result["used_reference_seed"] is True
    assert len(fake_generator.requests) == 1
    request = fake_generator.requests[0]
    assert request.reference_images == [b"seed-reference"]
    assert request.page_index is None

    prompt_body = json.loads(
        request.prompt[len(pt.PROMPT_PAGE_ILLUSTRATION_PREFACE) :].strip()
    )
    assert prompt_body["text_content"] == (
        f"Book title: {book.book_title}. Plot synopsis: {book.plot_synopsis}"
    )
    assert "This is a book cover illustration." in prompt_body["SYSTEM_NOTES"]["4"]


@pytest.mark.asyncio
async def test_generate_cover_from_reference_retries(monkeypatch):
    generator = RetryImageGenerator(failures_before_success=1)
    book = _make_book()

    monkeypatch.setattr(
        image_generation.image_service,
        "save_image",
        lambda image_data, relative_filepath: f"saved://{relative_filepath}",
    )
    monkeypatch.setattr(image_generation.settings, "image_generation_retry_attempts", 3)
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

    result = await generate_cover_from_reference(
        book,
        b"seed-reference",
        image_generator=generator,
    )

    assert result["attempt_count"] == 2
    assert generator.calls == 2
