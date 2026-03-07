import copy
import json
import asyncio
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from api.models.book_models import Page
from api.models.helpers import remove_book_model_relationships
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
    write_json_file,
)

logger = get_logger(__name__)


class ImageGenerationPipelineError(RuntimeError):
    pass


def make_illustration_prompt(page: Page, include_style: bool = True) -> str:
    illustration_prompt = pt.PROMPT_PAGE_ILLUSTRATION_BODY.copy()
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
    illustration_prompt["text_content"] = page.content.text_content_of_this_page
    illustration_prompt_str = json.dumps(illustration_prompt, indent=1)
    illustration_prompt_str = (
        f"{pt.PROMPT_PAGE_ILLUSTRATION_PREFACE}\n{illustration_prompt_str}"
    )
    return illustration_prompt_str


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
        images_dir: str,
        include_style: bool,
        reference_images: Optional[list[bytes]],
        used_reference_seed: bool,
    ) -> tuple[Dict[str, Any], bytes]:
        illustration_prompt = make_illustration_prompt(page, include_style=include_style)
        page.content.illustration_prompt = illustration_prompt
        request = ImageGenerationRequest(
            prompt=illustration_prompt,
            reference_images=reference_images,
            page_index=max(0, page.page_number - 1),
        )
        response = await self.image_generator.generate(request)
        filename = f"{page.page_number}.png"
        relative_filepath = f"{images_dir}/{filename}"
        saved_path = await asyncio.to_thread(
            image_service.save_image, response.image_bytes, relative_filepath
        )
        page.content.illustration = saved_path
        return (
            {
                "image_data": None,
                "provider": response.provider,
                "model": response.model,
                "saved_path": saved_path,
                "used_reference_seed": used_reference_seed,
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
    ) -> tuple[Dict[str, Any], bytes]:
        attempts = max(1, int(settings.image_generation_retry_attempts))
        for attempt in range(attempts):
            try:
                return await self._generate_and_save_page_once(
                    page=page,
                    images_dir=images_dir,
                    include_style=include_style,
                    reference_images=reference_images,
                    used_reference_seed=used_reference_seed,
                )
            except Exception as exc:
                page_index = max(0, page.page_number - 1)
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

    @abstractmethod
    async def generate(
        self,
        book,
        images_dir: str,
        progress: Optional[GenerationProgressEstimator] = None,
    ) -> Dict[int, Any]:
        ...


class LegacyIllustrationStrategy(IllustrationStrategy):
    async def generate(
        self,
        book,
        images_dir: str,
        progress: Optional[GenerationProgressEstimator] = None,
    ) -> Dict[int, Any]:
        illustrations = {}
        total_pages = len(book.pages)
        for idx, page in enumerate(book.pages, start=1):
            image_data, _ = await self._generate_and_save_page_with_retry(
                page=page,
                images_dir=images_dir,
                include_style=True,
                reference_images=None,
                used_reference_seed=False,
            )
            illustrations[page.page_number] = image_data
            logger.info(f"Generated illustration for page {page.page_number}")
            if progress:
                progress.mark_work_completed(
                    1.0,
                    note=f"Illustration generated for page {idx}/{total_pages}.",
                )
        return illustrations


class SeededReferenceEditStrategy(IllustrationStrategy):
    async def generate(
        self,
        book,
        images_dir: str,
        progress: Optional[GenerationProgressEstimator] = None,
    ) -> Dict[int, Any]:
        illustrations: Dict[int, Any] = {}
        total_pages = len(book.pages)
        if total_pages == 0:
            return illustrations

        seed_page = book.pages[0]
        seed_result, seed_image_bytes = await self._generate_and_save_page_with_retry(
            page=seed_page,
            images_dir=images_dir,
            include_style=True,
            reference_images=None,
            used_reference_seed=False,
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
        worker_count = self._determine_parallel_workers(len(remaining_pages))
        if not remaining_pages:
            return dict(sorted(illustrations.items()))

        semaphore = asyncio.Semaphore(worker_count)

        async def _generate_non_seed(page: Page, index_in_book: int):
            async with semaphore:
                image_data, _ = await self._generate_and_save_page_with_retry(
                    page=page,
                    images_dir=images_dir,
                    include_style=False,
                    reference_images=[seed_image_bytes],
                    used_reference_seed=True,
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

        tasks = [
            asyncio.create_task(_generate_non_seed(page, idx))
            for idx, page in enumerate(remaining_pages, start=2)
        ]
        try:
            results = await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        for page_number, image_data in results:
            illustrations[page_number] = image_data

        return dict(sorted(illustrations.items()))


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
    book, progress: GenerationProgressEstimator = None
) -> Dict[int, Any]:
    """
    Generates illustrations for all pages in a book and saves them appropriately.
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
    illustrations = await strategy.generate(book, images_dir, progress=progress)

    book_copy_no_refs = remove_book_model_relationships(copy.deepcopy(book))
    book_data = book_copy_no_refs.dict()
    metadata = {
        "book_id": str(book.book_id),
        "book_title": book.book_title,
    }

    filename = f"{book_id_str}.json"
    write_json_file(filename, book_data, relative_path=book_dir, metadata=metadata)
    logger.info(f"Saved book JSON for '{book.book_title}'")
    if progress:
        progress.set_stage("persisting_book_data")
        progress.mark_work_completed(1.0, note="Book JSON persisted.")

    return illustrations
