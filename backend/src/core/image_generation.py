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


STYLE_LEGACY_KEYS = (
    "Dimensionality/Depth",
    "Color Palette",
    "Line Quality",
    "Texture",
    "Character Style",
    "Perspective",
    "Movement",
    "Composition",
    "Use of Space",
    "Lighting",
    "Mood/Atmosphere",
    "Medium",
    "Detail Level",
)

CHARACTER_DUPLICATION_TRIGGER_PHRASES = (
    "same character appears twice",
    "two versions of",
    "three versions of",
    "several versions of",
    "repeated in the same image",
    "repeated in the same picture",
    "appears again in the same picture",
    "appears again in the same image",
    "montage",
    "comic strip",
    "storyboard",
    "sequence of poses",
)

CHARACTER_DUPLICATION_GENERIC_PHRASES = (
    "multiple",
    "more than one",
)

CHARACTER_DUPLICATION_RULE = (
    "Depict each listed character exactly once unless this prompt explicitly allows duplication for that character."
)
SINGLE_MOMENT_RULE = (
    "Render one continuous moment in time, not multiple beats or different moments from the same scene."
)
MOTION_WITHOUT_DUPLICATION_RULE = (
    "Show motion through pose, gesture, composition, and camera framing, not by repeating the same body multiple times."
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_legacy_style_attributes(style: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(style, dict):
        return {key: None for key in STYLE_LEGACY_KEYS}
    return {key: style.get(key) for key in STYLE_LEGACY_KEYS}


def _style_list(style: Optional[Dict[str, Any]], key: str) -> list[str]:
    if not isinstance(style, dict):
        return []
    value = style.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _style_text(style: Optional[Dict[str, Any]], key: str) -> Optional[str]:
    if not isinstance(style, dict):
        return None
    value = style.get(key)
    if value is None:
        return None
    return str(value)


def _build_style_prompt_fields(style: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    legacy_attributes = _extract_legacy_style_attributes(style)
    immutable_constraints = _style_list(style, "immutable_attributes")
    return {
        "illustration_style": legacy_attributes,
        "style_id": _style_text(style, "style_id"),
        "style_display_name": _style_text(style, "style_display_name"),
        "style_brief": _style_text(style, "style_brief"),
        "style_must_have_visual_traits": _style_list(
            style, "must_have_visual_traits"
        ),
        "style_must_not_have_visual_traits": _style_list(
            style, "must_not_have_visual_traits"
        ),
        "style_visual_anchor_cues": _style_list(style, "visual_anchor_cues"),
        "style_immutable_constraints": immutable_constraints,
        "style_flexible_guidance": _style_list(style, "flexible_attributes"),
        "style_execution_priority": [
            "Preserve the immutable style constraints first.",
            "Honor the style brief and visual anchor cues next.",
            "Let flexible guidance adapt framing, action, and composition without changing the overall style.",
        ],
        "style_consistency_goal": (
            "Keep the same core rendering language across the entire book while allowing page-specific action, poses, expressions, and camera framing to change."
        ),
        "style_reference_alignment": (
            "If a reference image is attached, treat it as the strongest example of the immutable style constraints and match it while still following the current page's scene description."
            if immutable_constraints
            else "If a reference image is attached, match its style while following the current page's scene description."
        ),
    }


def _extract_duplication_count(combined_text: str) -> Optional[int]:
    text = combined_text.lower()
    if any(phrase in text for phrase in ("three times", "3 times", "three versions of")):
        return 3
    if any(
        phrase in text
        for phrase in (
            "twice",
            "2 times",
            "two times",
            "same character appears twice",
            "two versions of",
        )
    ):
        return 2
    return None


def _build_character_duplication_fields(
    characters: list[dict[str, Any]],
    *,
    illustration_description: Optional[str],
    text_content: Optional[str],
) -> Dict[str, Any]:
    combined_text = " ".join(
        part for part in [illustration_description or "", text_content or ""] if part
    )
    lowered_text = combined_text.lower()
    explicit_duplication_triggered = any(
        phrase in lowered_text for phrase in CHARACTER_DUPLICATION_TRIGGER_PHRASES
    )
    character_names = [str(character.get("name")) for character in characters if character.get("name")]
    named_characters_in_text = [
        name for name in character_names if name.lower() in lowered_text
    ]
    generic_duplication_triggered = any(
        phrase in lowered_text for phrase in CHARACTER_DUPLICATION_GENERIC_PHRASES
    ) and bool(named_characters_in_text)
    duplication_triggered = explicit_duplication_triggered or generic_duplication_triggered

    allowed_duplicate_characters: list[str] = []
    if duplication_triggered:
        allowed_duplicate_characters = list(named_characters_in_text)
        if not allowed_duplicate_characters:
            allowed_duplicate_characters = character_names

    duplicate_count = _extract_duplication_count(combined_text)
    characters_with_counts = []
    for character in characters:
        count = 1
        if (
            duplicate_count is not None
            and character.get("name") in allowed_duplicate_characters
        ):
            count = duplicate_count
        characters_with_counts.append({**character, "count": count})

    summary_parts = [
        f"{character['name']}: {character['count']}"
        for character in characters_with_counts
        if character.get("name")
    ]
    summary = (
        "; ".join(summary_parts) if summary_parts else "No named characters specified."
    )

    duplication_rule = CHARACTER_DUPLICATION_RULE
    if allowed_duplicate_characters:
        duplication_rule = (
            "Duplication is intentional only for: "
            + ", ".join(allowed_duplicate_characters)
            + ". All other listed characters must appear exactly once."
        )

    return {
        "characters_in_illustration": characters_with_counts,
        "character_cardinality_summary": summary,
        "duplication_rule": duplication_rule,
        "single_moment_rule": SINGLE_MOMENT_RULE,
        "motion_without_duplication_rule": MOTION_WITHOUT_DUPLICATION_RULE,
        "allowed_duplicate_characters": allowed_duplicate_characters,
    }


def _humanize_style_name(style: Optional[Dict[str, Any]]) -> str:
    display_name = _style_text(style, "style_display_name")
    if display_name:
        return display_name
    style_id = _style_text(style, "style_id")
    if style_id:
        return style_id.replace("_", " ")
    return "selected illustration style"


def _top_style_traits(style: Optional[Dict[str, Any]], limit: int = 4) -> list[str]:
    prioritized = _style_list(style, "immutable_attributes")
    if len(prioritized) < limit:
        prioritized.extend(_style_list(style, "visual_anchor_cues"))
    seen: list[str] = []
    for trait in prioritized:
        if trait not in seen:
            seen.append(trait)
        if len(seen) >= limit:
            break
    return seen


def _build_style_prose_directive(
    style: Optional[Dict[str, Any]],
    *,
    use_reference: bool,
    is_cover: bool,
) -> str:
    style_name = _humanize_style_name(style)
    style_brief = _style_text(style, "style_brief") or "Keep the rendering visually distinctive."
    immutable_traits = _top_style_traits(style)
    negative_traits = _style_list(style, "must_not_have_visual_traits")[:3]

    lines = [
        f"Style directive: Use the {style_name} look. {style_brief}",
    ]
    if immutable_traits:
        lines.append(
            "Preserve these rendering traits above all else: "
            + "; ".join(immutable_traits)
            + "."
        )
    if negative_traits:
        lines.append(
            "Do not let the image drift into: "
            + "; ".join(negative_traits)
            + "."
        )
    if is_cover:
        lines.append(
            "Keep the same rendering language while allowing a stronger, more iconic cover composition and focal hierarchy."
        )
    else:
        lines.append(
            "Character action, posing, and camera framing may change from page to page, but the rendering language must stay in this same style family."
        )
    if use_reference:
        lines.append(
            "Use any attached reference image only to reinforce this same style direction; it must match the prose style directive rather than replace it."
        )
    return "\n".join(lines)


def make_illustration_prompt(
    page: Page, include_style: bool = True, prompt_path_version: Optional[str] = None
) -> str:
    selected_prompt_path_version = prompt_path_version or settings.prompt_path_version
    style = page.book_parent.illustration_style
    illustration_prompt = copy.deepcopy(pt.PROMPT_PAGE_ILLUSTRATION_BODY)
    illustration_prompt["SYSTEM_NOTES"] = dict(
        pt.PROMPT_PAGE_ILLUSTRATION_BODY.get("SYSTEM_NOTES", {})
    )
    illustration_prompt.update(_build_style_prompt_fields(style))
    if include_style:
        illustration_prompt["SYSTEM_NOTES"]["12"] = (
            "Use the style brief, must-have traits, negative constraints, anchor cues, and immutable constraints below as hard style guidance."
        )
    else:
        illustration_prompt["SYSTEM_NOTES"]["12"] = (
            f"{pt.PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE} Treat the attached image as the strongest style reference for the immutable constraints below."
        )
    illustration_prompt["illustration_description"] = page.content.illustration
    characters_in_illustration = [
        {"name": cinfo.name, "appearance": cinfo.appearance}
        for cinfo in page.content.characters_in_this_page_data
    ]
    illustration_prompt.update(
        _build_character_duplication_fields(
            characters_in_illustration,
            illustration_description=page.content.illustration,
            text_content=page.content.text_content_of_this_page,
        )
    )
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
    prose_style_directive = _build_style_prose_directive(
        style,
        use_reference=not include_style,
        is_cover=False,
    )
    illustration_prompt_str = json.dumps(illustration_prompt, indent=1)
    illustration_prompt_str = (
        f"{prose_style_directive}\n{pt.PROMPT_PAGE_ILLUSTRATION_PREFACE}\n{illustration_prompt_str}"
    )
    return illustration_prompt_str


def make_cover_prompt(book: Book, prompt_path_version: Optional[str] = None) -> str:
    selected_prompt_path_version = prompt_path_version or settings.prompt_path_version
    style = book.illustration_style
    cover_prompt = copy.deepcopy(pt.PROMPT_PAGE_ILLUSTRATION_BODY)
    cover_prompt["SYSTEM_NOTES"] = dict(
        pt.PROMPT_PAGE_ILLUSTRATION_BODY.get("SYSTEM_NOTES", {})
    )
    cover_prompt["SYSTEM_NOTES"]["12"] = (
        "This is a book cover illustration. Compose a dynamic, title-forward scene without any rendered text."
    )
    cover_prompt["SYSTEM_NOTES"]["13"] = (
        "No letters, words, numbers, logos, captions, or speech bubbles in the final image."
    )
    cover_prompt["SYSTEM_NOTES"]["14"] = (
        f"{pt.PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE} Keep the cover in the same style family as the interior pages while allowing a stronger focal composition."
    )
    cover_prompt["SYSTEM_NOTES"]["15"] = (
        "Preserve immutable style constraints from the selected style and any reference image, but allow the cover composition to be more iconic and title-forward."
    )
    cover_prompt.update(_build_style_prompt_fields(style))
    cover_prompt["illustration_description"] = (
        "Create a visually striking, toddler-friendly cover image that captures the heart of the story. "
        f"Story title context: {book.book_title}. "
        "Show characters in clear action with expressive faces, strong foreground subject focus, and a cohesive scene."
    )
    cover_text_content = f"Book title: {book.book_title}. Plot synopsis: {book.plot_synopsis}"
    cover_characters = [
        {"name": c.name, "appearance": c.appearance} for c in book.characters
    ]
    cover_prompt.update(
        _build_character_duplication_fields(
            cover_characters,
            illustration_description=cover_prompt["illustration_description"],
            text_content=cover_text_content,
        )
    )
    if selected_prompt_path_version in {"v2", "v3"} and getattr(book, "settings", None):
        cover_prompt["settings_visual_anchor_details"] = [
            {"setting_name": s.name, "visual_anchor_details": s.visual_anchor_details}
            for s in book.settings
        ]
    cover_prompt["text_content"] = cover_text_content
    prose_style_directive = _build_style_prose_directive(
        style,
        use_reference=True,
        is_cover=True,
    )
    cover_prompt_str = json.dumps(cover_prompt, indent=1)
    return (
        f"{prose_style_directive}\n{pt.PROMPT_PAGE_ILLUSTRATION_PREFACE}\n{cover_prompt_str}"
    )


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


async def generate_cover_from_reference(
    book: Book,
    reference_image_bytes: bytes,
    *,
    strategy_name: Optional[str] = None,
    image_generator: Optional[ImageGenerator] = None,
    prompt_path_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generates only the cover image for an existing book using a provided seed reference.
    """
    if not reference_image_bytes:
        raise ValueError("reference_image_bytes is required to generate a cover.")

    book_id_str = str(book.book_id)
    book_dir = construct_storage_path(book_id_str)

    if not settings.use_cloud_storage:
        ensure_directory_exists(book_dir)

    strategy = get_illustration_strategy(
        strategy_name=strategy_name,
        image_generator=image_generator,
    )
    return await strategy._generate_cover_with_retry(
        book=book,
        book_dir=book_dir,
        reference_images=[reference_image_bytes],
        used_reference_seed=True,
        prompt_path_version=prompt_path_version or settings.prompt_path_version,
    )
