import copy
import json
import asyncio
import hashlib
import random
import time
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from api.models.book_models import Book, Page
from config import settings
from core.progress_estimation import GenerationProgressEstimator
from core.prompts import prompts as pt
from services import image_service
from services.image_generation_provider import (
    ImageGenerationRequest,
    ImageGenerator,
    OpenAIImageGenerator,
    build_image_generator,
)
from utils.general_utils import (
    construct_storage_path,
    ensure_directory_exists,
    get_logger,
)

logger = get_logger(__name__)


class ImageGenerationPipelineError(RuntimeError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_illustration_prompt(
    page: Page, include_style: bool = True, prompt_path_version: Optional[str] = None
) -> str:
    selected_prompt_path_version = prompt_path_version or settings.prompt_path_version
    illustration_prompt = copy.deepcopy(pt.PROMPT_PAGE_ILLUSTRATION_BODY)
    illustration_prompt["SYSTEM_NOTES"] = dict(
        pt.PROMPT_PAGE_ILLUSTRATION_BODY.get("SYSTEM_NOTES", {})
    )
    if include_style:
        illustration_prompt["illustration_style"] = page.book_parent.illustration_style
    else:
        illustration_prompt.pop("illustration_style", None)
        illustration_prompt["SYSTEM_NOTES"]["4"] = (
            pt.PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE
        )
    illustration_prompt["illustration_description"] = page.content.illustration
    illustration_prompt["characters_in_illustration"] = [
        {"name": cinfo.name, "appearance": cinfo.appearance}
        for cinfo in page.content.characters_in_this_page_data
    ]
    if (
        selected_prompt_path_version in {"v2", "v3"}
        and getattr(page, "setting_id", None)
        and getattr(page, "book_parent", None)
    ):
        setting = next(
            (
                s
                for s in getattr(page.book_parent, "settings", [])
                if s.id == page.setting_id
            ),
            None,
        )
        if setting is None:
            raise ValueError(
                f"Unable to resolve setting for page_number={page.page_number} with setting_id={page.setting_id}"
            )
        illustration_prompt["setting_name"] = setting.name
        illustration_prompt["setting_visual_anchor_details"] = (
            setting.visual_anchor_details
        )
    illustration_prompt["text_content"] = page.content.text_content_of_this_page
    illustration_prompt_str = json.dumps(illustration_prompt, indent=1)
    illustration_prompt_str = (
        f"{pt.PROMPT_PAGE_ILLUSTRATION_PREFACE}\n{illustration_prompt_str}"
    )
    return illustration_prompt_str


def make_cover_prompt(book: Book, prompt_path_version: Optional[str] = None) -> str:
    selected_prompt_path_version = prompt_path_version or settings.prompt_path_version
    cover_prompt = copy.deepcopy(pt.PROMPT_PAGE_ILLUSTRATION_BODY)
    cover_prompt["SYSTEM_NOTES"] = dict(pt.PROMPT_PAGE_ILLUSTRATION_BODY.get("SYSTEM_NOTES", {}))
    cover_prompt["SYSTEM_NOTES"]["4"] = (
        "This is a book cover illustration. Compose a dynamic, title-forward scene without any rendered text."
    )
    cover_prompt["SYSTEM_NOTES"]["5"] = (
        "No letters, words, numbers, logos, captions, or speech bubbles in the final image."
    )
    cover_prompt["SYSTEM_NOTES"]["6"] = (
        pt.PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE
    )
    cover_prompt["illustration_style"] = book.illustration_style
    cover_prompt["illustration_description"] = (
        "Create a visually striking, toddler-friendly cover image that captures the heart of the story. "
        f"Story title context: {book.book_title}. "
        "Show characters in clear action with expressive faces, strong foreground subject focus, and a cohesive scene."
    )
    cover_prompt["characters_in_illustration"] = [
        {"name": c.name, "appearance": c.appearance} for c in book.characters
    ]
    if selected_prompt_path_version in {"v2", "v3"} and getattr(book, "settings", None):
        cover_prompt["settings_visual_anchor_details"] = [
            {"setting_name": s.name, "visual_anchor_details": s.visual_anchor_details}
            for s in book.settings
        ]
    cover_prompt["text_content"] = (
        f"Book title: {book.book_title}. Plot synopsis: {book.plot_synopsis}"
    )
    cover_prompt_str = json.dumps(cover_prompt, indent=1)
    return f"{pt.PROMPT_PAGE_ILLUSTRATION_PREFACE}\n{cover_prompt_str}"


async def generate_single_page_illustration(
    page: Page,
    illustration_prompt: str,
    images_dir: str,
    image_generator: Optional[ImageGenerator] = None,
    reference_images: Optional[list[bytes]] = None,
) -> Dict[str, Any]:
    """
    Generates an illustration for a single page and saves the image.
    """
    generator = image_generator or OpenAIImageGenerator()
    request = ImageGenerationRequest(
        prompt=illustration_prompt,
        reference_images=reference_images,
        page_index=max(0, page.page_number - 1),
        image_kind="page",
    )
    page.content.illustration_prompt = illustration_prompt

    try:
        response = await generator.generate(request)
        filename = f"{page.page_number}.png"
        relative_filepath = f"{images_dir}/{filename}"
        saved_path = image_service.save_image(response.image_bytes, relative_filepath)

        # Intermediate write; content_generation later replaces this with signed-url metadata.
        page.content.illustration = saved_path
        logger.debug(
            "Saved page %s illustration with provider=%s model=%s to %s",
            page.page_number,
            response.provider,
            response.model,
            saved_path,
        )
        return {
            "image_data": None,
            "provider": response.provider,
            "model": response.model,
            "saved_path": saved_path,
        }
    except Exception as exc:
        page_index = max(0, page.page_number - 1)
        raise ImageGenerationPipelineError(
            f"Image generation failed at page_index={page_index}, "
            f"provider={generator.provider}, model={generator.model}: {exc}"
        ) from exc


class IllustrationStrategy(ABC):
    def __init__(self, image_generator: ImageGenerator) -> None:
        self.image_generator = image_generator

    @staticmethod
    def _determine_parallel_workers(remaining_pages: int) -> int:
        if remaining_pages <= 0:
            return 0
        if remaining_pages == 1:
            return 1
        min_workers = max(1, int(settings.image_generation_min_workers))
        max_workers = max(min_workers, int(settings.image_generation_max_workers))
        return min(remaining_pages, max_workers, max(min_workers, remaining_pages))

    @staticmethod
    def _retry_delay_seconds(attempt_index: int) -> float:
        base = max(0.0, float(settings.image_generation_retry_backoff_base_seconds))
        max_delay = max(base, float(settings.image_generation_retry_backoff_max_seconds))
        delay = min(max_delay, base * (2**attempt_index))
        if settings.image_generation_retry_use_jitter and delay > 0:
            return random.uniform(0.0, delay)
        return delay

    async def _generate_and_save_page_once(
        self,
        page: Page,
        illustration_prompt: str,
        images_dir: str,
        reference_images: Optional[list[bytes]],
        used_reference_seed: bool,
    ) -> tuple[Dict[str, Any], bytes]:
        started = time.monotonic()
        request = ImageGenerationRequest(
            prompt=illustration_prompt,
            reference_images=reference_images,
            page_index=max(0, page.page_number - 1),
            image_kind="page",
        )
        response = await self.image_generator.generate(request)
        filename = f"{page.page_number}.png"
        relative_filepath = f"{images_dir}/{filename}"
        saved_path = await asyncio.to_thread(
            image_service.save_image, response.image_bytes, relative_filepath
        )
        page.content.illustration = saved_path
        duration_seconds = round(time.monotonic() - started, 3)
        return (
            {
                "image_data": None,
                "provider": response.provider,
                "model": response.model,
                "saved_path": saved_path,
                "used_reference_seed": used_reference_seed,
                "generation_duration_seconds": duration_seconds,
            },
            response.image_bytes,
        )

    async def _generate_and_save_page_with_retry(
        self,
        page: Page,
        images_dir: str,
        include_style: bool,
        reference_images: Optional[list[bytes]],
        used_reference_seed: bool,
        prompt_path_version: Optional[str] = None,
    ) -> tuple[Dict[str, Any], bytes]:
        attempts = max(1, int(settings.image_generation_retry_attempts))
        illustration_prompt = make_illustration_prompt(
            page,
            include_style=include_style,
            prompt_path_version=prompt_path_version,
        )
        page.content.illustration_prompt = illustration_prompt
        attempt_records = []
        overall_started = time.monotonic()

        for attempt in range(attempts):
            attempt_started_at = _utcnow_iso()
            attempt_monotonic_start = time.monotonic()
            try:
                image_data, image_bytes = await self._generate_and_save_page_once(
                    page=page,
                    illustration_prompt=illustration_prompt,
                    images_dir=images_dir,
                    reference_images=reference_images,
                    used_reference_seed=used_reference_seed,
                )
                attempt_records.append(
                    {
                        "attempt_number": attempt + 1,
                        "status": "success",
                        "started_at": attempt_started_at,
                        "duration_seconds": round(
                            time.monotonic() - attempt_monotonic_start, 3
                        ),
                    }
                )
                image_data.update(
                    {
                        "page_number": page.page_number,
                        "attempt_count": attempt + 1,
                        "attempts": attempt_records,
                        "illustration_prompt": illustration_prompt,
                        "illustration_prompt_char_count": len(illustration_prompt),
                        "illustration_prompt_sha256": _sha256_text(illustration_prompt),
                        "total_duration_seconds": round(
                            time.monotonic() - overall_started, 3
                        ),
                    }
                )
                return image_data, image_bytes
            except Exception as exc:
                page_index = max(0, page.page_number - 1)
                attempt_records.append(
                    {
                        "attempt_number": attempt + 1,
                        "status": "error",
                        "started_at": attempt_started_at,
                        "duration_seconds": round(
                            time.monotonic() - attempt_monotonic_start, 3
                        ),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                if attempt == attempts - 1:
                    raise ImageGenerationPipelineError(
                        f"Image generation failed at page_index={page_index}, "
                        f"page_number={page.page_number}, "
                        f"provider={self.image_generator.provider}, "
                        f"model={self.image_generator.model} after {attempts} attempts: {exc}"
                    ) from exc
                delay = self._retry_delay_seconds(attempt)
                logger.warning(
                    "Retrying image generation for page_number=%s page_index=%s "
                    "provider=%s model=%s attempt=%s/%s delay=%.2fs",
                    page.page_number,
                    page_index,
                    self.image_generator.provider,
                    self.image_generator.model,
                    attempt + 2,
                    attempts,
                    delay,
                )
                if delay > 0:
                    await asyncio.sleep(delay)

    async def _generate_cover_once(
        self,
        book: Book,
        cover_prompt: str,
        cover_relative_filepath: str,
        reference_images: Optional[list[bytes]],
        used_reference_seed: bool,
    ) -> tuple[Dict[str, Any], bytes]:
        started = time.monotonic()
        request = ImageGenerationRequest(
            prompt=cover_prompt,
            reference_images=reference_images,
            page_index=None,
            image_kind="cover",
        )
        response = await self.image_generator.generate(request)
        saved_path = await asyncio.to_thread(
            image_service.save_image, response.image_bytes, cover_relative_filepath
        )
        duration_seconds = round(time.monotonic() - started, 3)
        return (
            {
                "provider": response.provider,
                "model": response.model,
                "saved_path": saved_path,
                "used_reference_seed": used_reference_seed,
                "generation_duration_seconds": duration_seconds,
            },
            response.image_bytes,
        )

    async def _generate_cover_with_retry(
        self,
        book: Book,
        book_dir: str,
        reference_images: Optional[list[bytes]],
        used_reference_seed: bool,
        prompt_path_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        attempts = max(1, int(settings.image_generation_retry_attempts))
        cover_prompt = make_cover_prompt(book, prompt_path_version=prompt_path_version)
        attempt_records = []
        overall_started = time.monotonic()
        cover_relative_filepath = f"{book_dir}/cover.png"

        for attempt in range(attempts):
            attempt_started_at = _utcnow_iso()
            attempt_monotonic_start = time.monotonic()
            try:
                cover_data, _ = await self._generate_cover_once(
                    book=book,
                    cover_prompt=cover_prompt,
                    cover_relative_filepath=cover_relative_filepath,
                    reference_images=reference_images,
                    used_reference_seed=used_reference_seed,
                )
                attempt_records.append(
                    {
                        "attempt_number": attempt + 1,
                        "status": "success",
                        "started_at": attempt_started_at,
                        "duration_seconds": round(
                            time.monotonic() - attempt_monotonic_start, 3
                        ),
                    }
                )
                cover_data.update(
                    {
                        "attempt_count": attempt + 1,
                        "attempts": attempt_records,
                        "cover_prompt": cover_prompt,
                        "cover_prompt_char_count": len(cover_prompt),
                        "cover_prompt_sha256": _sha256_text(cover_prompt),
                        "total_duration_seconds": round(
                            time.monotonic() - overall_started, 3
                        ),
                    }
                )
                return cover_data
            except Exception as exc:
                attempt_records.append(
                    {
                        "attempt_number": attempt + 1,
                        "status": "error",
                        "started_at": attempt_started_at,
                        "duration_seconds": round(
                            time.monotonic() - attempt_monotonic_start, 3
                        ),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                if attempt == attempts - 1:
                    raise ImageGenerationPipelineError(
                        f"Cover image generation failed for book_id={book.book_id}, "
                        f"provider={self.image_generator.provider}, "
                        f"model={self.image_generator.model} after {attempts} attempts: {exc}"
                    ) from exc
                delay = self._retry_delay_seconds(attempt)
                logger.warning(
                    "Retrying cover generation for book_id=%s provider=%s model=%s "
                    "attempt=%s/%s delay=%.2fs",
                    book.book_id,
                    self.image_generator.provider,
                    self.image_generator.model,
                    attempt + 2,
                    attempts,
                    delay,
                )
                if delay > 0:
                    await asyncio.sleep(delay)

    @abstractmethod
    async def generate(
        self,
        book,
        book_dir: str,
        images_dir: str,
        progress: Optional[GenerationProgressEstimator] = None,
        prompt_path_version: Optional[str] = None,
    ) -> tuple[Dict[int, Any], Dict[str, Any]]:
        ...


class LegacyIllustrationStrategy(IllustrationStrategy):
    async def generate(
        self,
        book,
        book_dir: str,
        images_dir: str,
        progress: Optional[GenerationProgressEstimator] = None,
        prompt_path_version: Optional[str] = None,
    ) -> tuple[Dict[int, Any], Dict[str, Any]]:
        illustrations = {}
        seed_image_bytes: Optional[bytes] = None
        total_pages = len(book.pages)
        for idx, page in enumerate(book.pages, start=1):
            image_data, page_image_bytes = await self._generate_and_save_page_with_retry(
                page=page,
                images_dir=images_dir,
                include_style=True,
                reference_images=None,
                used_reference_seed=False,
                prompt_path_version=prompt_path_version,
            )
            if idx == 1:
                seed_image_bytes = page_image_bytes
            illustrations[page.page_number] = image_data
            logger.info(f"Generated illustration for page {page.page_number}")
            if progress:
                progress.mark_work_completed(
                    1.0,
                    note=f"Illustration generated for page {idx}/{total_pages}.",
                )
        cover_result = await self._generate_cover_with_retry(
            book=book,
            book_dir=book_dir,
            reference_images=[seed_image_bytes] if seed_image_bytes else None,
            used_reference_seed=seed_image_bytes is not None,
            prompt_path_version=prompt_path_version,
        )
        if progress:
            progress.mark_work_completed(1.0, note="Cover generated.")
        return illustrations, cover_result


class SeededReferenceEditStrategy(IllustrationStrategy):
    async def generate(
        self,
        book,
        book_dir: str,
        images_dir: str,
        progress: Optional[GenerationProgressEstimator] = None,
        prompt_path_version: Optional[str] = None,
    ) -> tuple[Dict[int, Any], Dict[str, Any]]:
        illustrations: Dict[int, Any] = {}
        total_pages = len(book.pages)
        if total_pages == 0:
            raise ImageGenerationPipelineError(
                "Cannot generate a cover without any pages to establish visual style."
            )

        seed_page = book.pages[0]
        seed_result, seed_image_bytes = await self._generate_and_save_page_with_retry(
            page=seed_page,
            images_dir=images_dir,
            include_style=True,
            reference_images=None,
            used_reference_seed=False,
            prompt_path_version=prompt_path_version,
        )
        illustrations[seed_page.page_number] = seed_result
        logger.info(
            "Generated seed illustration for page %s with seeded strategy.",
            seed_page.page_number,
        )
        if progress:
            progress.mark_work_completed(
                1.0,
                note=f"Illustration generated for page 1/{total_pages}.",
            )

        remaining_pages = book.pages[1:]
        worker_count = self._determine_parallel_workers(len(remaining_pages) + 1)

        semaphore = asyncio.Semaphore(worker_count)

        async def _generate_non_seed(page: Page, index_in_book: int):
            async with semaphore:
                image_data, _ = await self._generate_and_save_page_with_retry(
                    page=page,
                    images_dir=images_dir,
                    include_style=False,
                    reference_images=[seed_image_bytes],
                    used_reference_seed=True,
                    prompt_path_version=prompt_path_version,
                )
                logger.info(
                    "Generated illustration for page %s with seeded strategy.",
                    page.page_number,
                )
                if progress:
                    progress.mark_work_completed(
                        1.0,
                        note=f"Illustration generated for page {index_in_book}/{total_pages}.",
                    )
                return page.page_number, image_data

        async def _generate_cover():
            async with semaphore:
                cover_data = await self._generate_cover_with_retry(
                    book=book,
                    book_dir=book_dir,
                    reference_images=[seed_image_bytes],
                    used_reference_seed=True,
                    prompt_path_version=prompt_path_version,
                )
                if progress:
                    progress.mark_work_completed(1.0, note="Cover generated.")
                return cover_data

        tasks = [
            asyncio.create_task(_generate_non_seed(page, idx))
            for idx, page in enumerate(remaining_pages, start=2)
        ]
        cover_task = asyncio.create_task(_generate_cover())
        try:
            results = await asyncio.gather(*tasks, cover_task)
        except Exception:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if not cover_task.done():
                cover_task.cancel()
            await asyncio.gather(*tasks, cover_task, return_exceptions=True)
            raise

        cover_result = results[-1]
        page_results = results[:-1]
        for page_number, image_data in page_results:
            illustrations[page_number] = image_data

        return dict(sorted(illustrations.items())), cover_result


def get_illustration_strategy(
    strategy_name: Optional[str] = None,
    image_generator: Optional[ImageGenerator] = None,
) -> IllustrationStrategy:
    selected_strategy = strategy_name or settings.image_generation_strategy
    generator = image_generator or build_image_generator()

    if selected_strategy == "legacy":
        return LegacyIllustrationStrategy(generator)
    if selected_strategy == "seeded_reference_edit":
        return SeededReferenceEditStrategy(generator)
    raise ValueError(
        f"Unsupported image generation strategy '{selected_strategy}'. "
        "Supported strategies: legacy, seeded_reference_edit."
    )


async def generate_page_illustrations(
    book,
    progress: GenerationProgressEstimator = None,
    prompt_path_version: Optional[str] = None,
    artifact_context: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[int, Any], Dict[str, Any]]:
    """
    Generates and saves page illustrations for all pages in a book.
    """
    illustrations = {}
    logger.info(f"Generating illustrations for the book '{book.book_title}'")

    book_id_str = str(book.book_id)
    logger.debug(f"Using book_id for directory names: {book_id_str}")

    book_dir = construct_storage_path(book_id_str)
    images_dir = construct_storage_path(f"{book_id_str}/images")
    logger.debug(f"Constructed book_dir: {book_dir}")
    logger.debug(f"Constructed images_dir: {images_dir}")

    if not settings.use_cloud_storage:
        ensure_directory_exists(book_dir)
        ensure_directory_exists(images_dir)
    logger.info(f"Directories ensured for book '{book.book_title}'")

    strategy = get_illustration_strategy()
    illustrations, cover_result = await strategy.generate(
        book,
        book_dir,
        images_dir,
        progress=progress,
        prompt_path_version=prompt_path_version or settings.prompt_path_version,
    )
    if artifact_context is not None:
        artifact_context["strategy"] = strategy.__class__.__name__
        artifact_context["page_results"] = [
            illustrations[pn] for pn in sorted(illustrations.keys())
        ]
        artifact_context["page_count"] = len(illustrations)
        artifact_context["cover_result"] = cover_result

    return illustrations, cover_result
