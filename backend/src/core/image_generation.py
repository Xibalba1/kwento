import copy
import json
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
    if include_style:
        illustration_prompt["illustration_style"] = page.book_parent.illustration_style
    else:
        illustration_prompt.pop("illustration_style", None)
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
            illustration_prompt = make_illustration_prompt(page)
            image_data = await generate_single_page_illustration(
                page,
                illustration_prompt,
                images_dir,
                image_generator=self.image_generator,
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
        illustrations = {}
        total_pages = len(book.pages)
        seed_image_bytes: Optional[bytes] = None

        for idx, page in enumerate(book.pages, start=1):
            try:
                # For seeded strategy, include explicit style only for seed page.
                illustration_prompt = make_illustration_prompt(
                    page, include_style=(idx == 1)
                )
                reference_images = [seed_image_bytes] if seed_image_bytes else None
                request = ImageGenerationRequest(
                    prompt=illustration_prompt,
                    reference_images=reference_images,
                    page_index=idx - 1,
                )
                page.content.illustration_prompt = illustration_prompt
                response = await self.image_generator.generate(request)
                if seed_image_bytes is None:
                    seed_image_bytes = response.image_bytes

                filename = f"{page.page_number}.png"
                relative_filepath = f"{images_dir}/{filename}"
                saved_path = image_service.save_image(
                    response.image_bytes, relative_filepath
                )
                page.content.illustration = saved_path
                illustrations[page.page_number] = {
                    "image_data": None,
                    "provider": response.provider,
                    "model": response.model,
                    "saved_path": saved_path,
                    "used_reference_seed": seed_image_bytes is not None and idx > 1,
                }
                logger.info(
                    "Generated illustration for page %s with seeded strategy.",
                    page.page_number,
                )
                if progress:
                    progress.mark_work_completed(
                        1.0,
                        note=f"Illustration generated for page {idx}/{total_pages}.",
                    )
            except Exception as exc:
                raise ImageGenerationPipelineError(
                    f"Seeded strategy failed at page_index={idx - 1}, "
                    f"page_number={page.page_number}, "
                    f"provider={self.image_generator.provider}, "
                    f"model={self.image_generator.model}: {exc}"
                ) from exc
        return illustrations


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
