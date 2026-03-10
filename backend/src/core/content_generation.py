# backend/src/core/content_generation.py

import json
import random
import time
import hashlib
import inspect
from datetime import datetime, timezone, timedelta
from pathlib import Path
from config import settings
from typing import Dict, Any, Optional
from services.text_generation_provider import build_text_generator, TextGenerationResult
from api.models.book_models import Book
from api.models.helpers import assign_book_model_relationships, remove_book_model_relationships
from core.prompts import prompts as pt
from core.image_generation import generate_page_illustrations
from core.progress_estimation import GenerationProgressEstimator
from utils.general_utils import (
    construct_storage_path,
    ensure_directory_exists,
    generate_presigned_url,
    get_logger,
    write_json_file,
)

logger = get_logger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _capture_stage_duration(
    stage_timings: Dict[str, float], stage_name: str, started: float
) -> None:
    stage_timings[stage_name] = round(time.monotonic() - started, 3)


def _build_generation_run_artifact(
    *,
    request_id: Optional[str],
    theme: str,
    prompt_path_version: str,
) -> Dict[str, Any]:
    return {
        "artifact_type": "generation_run",
        "artifact_version": "v1",
        "run": {
            "request_id": request_id,
            "status": "in_progress",
            "started_at": _utcnow_iso(),
            "finished_at": None,
            "total_duration_seconds": None,
            "error": None,
        },
        "input": {
            "theme": theme,
            "theme_char_count": len(theme),
            "theme_sha256": _sha256_text(theme),
            "theme_normalized": theme.strip(),
        },
        "configuration_snapshot": {
            "prompt_path_version": prompt_path_version,
            "image_generation_strategy": settings.image_generation_strategy,
            "text_provider": settings.text_provider,
            "image_provider": settings.image_provider,
            "text_model": {
                "openai": settings.openai_text_model,
                "google": settings.google_text_model,
            }.get(settings.text_provider),
            "image_model": {
                "openai": settings.openai_image_model,
                "google": settings.google_image_model,
            }.get(settings.image_provider),
            "retry": {
                "attempts": settings.image_generation_retry_attempts,
                "backoff_base_seconds": settings.image_generation_retry_backoff_base_seconds,
                "backoff_max_seconds": settings.image_generation_retry_backoff_max_seconds,
                "use_jitter": settings.image_generation_retry_use_jitter,
            },
            "parallelism": {
                "min_workers": settings.image_generation_min_workers,
                "max_workers": settings.image_generation_max_workers,
            },
            "openai_image": {
                "aspect_profile": settings.openai_image_aspect_profile,
                "size_override": settings.openai_image_size_override,
                "quality_mode": settings.openai_image_quality_mode,
                "output_format": settings.openai_image_output_format,
                "output_compression": settings.openai_image_output_compression,
                "background": settings.openai_image_background,
            },
            "google_image": {
                "aspect_ratio": settings.google_image_aspect_ratio,
                "image_size": settings.google_image_size,
            },
            "storage": {
                "use_cloud_storage": settings.use_cloud_storage,
                "gcs_bucket_name": settings.gcs_bucket_name if settings.use_cloud_storage else None,
                "local_data_path": settings.local_data_path if not settings.use_cloud_storage else None,
            },
        },
        "story_generation": {
            "prompt_full_text": None,
            "response_raw_json": None,
            "parse_status": "not_started",
            "text_provider": None,
            "text_model": None,
            "response_id": None,
            "usage": None,
            "latency_seconds": None,
        },
        "image_generation": {
            "strategy": settings.image_generation_strategy,
            "duration_seconds": None,
            "page_count": 0,
            "pages": [],
        },
        "timing": {"stages": {}},
        "cost_analytics": {
            "text_prompt_tokens": None,
            "text_completion_tokens": None,
            "text_total_tokens": None,
            "image_count_requested": None,
            "image_count_generated": None,
            "estimated_text_cost_usd": None,
            "estimated_image_cost_usd": None,
            "estimated_total_cost_usd": None,
        },
    }


def _to_text_generation_result(
    result: Any, provider: str, model: str
) -> TextGenerationResult:
    if isinstance(result, TextGenerationResult):
        return result
    if isinstance(result, str):
        return TextGenerationResult(content=result, provider=provider, model=model)
    raise TypeError(f"Unexpected text generation result type: {type(result).__name__}")


def _persist_generation_artifact(
    artifact: Dict[str, Any],
    *,
    request_id: Optional[str],
    book_id: Optional[str],
) -> None:
    status = artifact["run"]["status"]
    file_name = "generation_run.json" if book_id else f"{request_id or 'unknown'}.json"
    relative_path = (
        construct_storage_path(book_id)
        if book_id
        else construct_storage_path("_generation_failures")
    )
    if not settings.use_cloud_storage:
        ensure_directory_exists(relative_path)

    metadata = {
        "artifact_type": "generation_run",
        "book_id": book_id or "",
        "request_id": request_id or "",
        "status": status,
    }
    write_json_file(
        file_name=file_name,
        data=artifact,
        relative_path=relative_path,
        metadata=metadata,
    )


def _extract_partial_image_page_data(book: Optional[Book]) -> list[Dict[str, Any]]:
    if book is None:
        return []

    pages: list[Dict[str, Any]] = []
    for page in sorted(book.pages, key=lambda p: p.page_number):
        prompt = page.content.illustration_prompt
        saved_path = (
            page.content.illustration
            if isinstance(page.content.illustration, str)
            else None
        )
        if prompt is None and saved_path is None:
            continue
        pages.append(
            {
                "page_number": page.page_number,
                "illustration_prompt": prompt,
                "illustration_prompt_char_count": len(prompt) if prompt else 0,
                "illustration_prompt_sha256": _sha256_text(prompt) if prompt else None,
                "saved_path": saved_path,
                "status": "partial",
            }
        )
    return pages


def build_story_prompt(theme: str, prompt_path_version: str) -> str:
    if prompt_path_version == "v1":
        master_prompt = pt.PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS.format(theme=theme)
        output_example = pt.TEMPLATE_CHILDRENS_BOOK
    elif prompt_path_version == "v2":
        master_prompt = pt.PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS_V2.format(theme=theme)
        output_example = pt.TEMPLATE_CHILDRENS_BOOK_V2
    elif prompt_path_version == "v3":
        master_prompt = pt.PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS_V3.format(theme=theme)
        output_example = pt.TEMPLATE_CHILDRENS_BOOK_V3
    else:
        raise ValueError(
            f"Unsupported prompt_path_version '{prompt_path_version}'. Supported values: v1, v2, v3."
        )
    return f"{master_prompt}\n{output_example}"


def validate_book_for_prompt_path(book: Book, prompt_path_version: str) -> None:
    if prompt_path_version not in {"v2", "v3"}:
        return
    if not book.settings:
        raise ValueError(
            f"prompt_path_version={prompt_path_version} requires a non-empty top-level 'settings' array."
        )
    setting_ids = {setting.id for setting in book.settings if setting.id}
    if len(setting_ids) != len(book.settings):
        raise ValueError(
            f"prompt_path_version={prompt_path_version} requires unique, non-empty setting ids in 'settings'."
        )
    for page in book.pages:
        if not page.setting_id:
            raise ValueError(
                f"prompt_path_version={prompt_path_version} requires 'setting_id' on page_number={page.page_number}."
            )
        if page.setting_id not in setting_ids:
            raise ValueError(
                f"Page {page.page_number} references unknown setting_id '{page.setting_id}'."
            )


async def generate_book(theme: str, request_id: Optional[str] = None) -> Book:
    progress = GenerationProgressEstimator(
        logger=logger,
        enabled=settings.enable_generation_progress_estimation,
        log_interval_seconds=settings.generation_progress_log_interval_seconds,
    )
    started_at = time.monotonic()
    stage_timings: Dict[str, float] = {}
    success = False
    failure_error: Optional[Exception] = None
    book: Optional[Book] = None
    book_id_str: Optional[str] = None
    prompt_path_version = settings.prompt_path_version
    generation_artifact = _build_generation_run_artifact(
        request_id=request_id,
        theme=theme,
        prompt_path_version=prompt_path_version,
    )

    await progress.start()
    try:
        progress.set_stage("generating_story")
        progress.add_total_work(1.0)
        logger.info(f"Generating book with theme: {theme}")
        logger.info(
            "Using story prompt path version '%s' for book generation.",
            prompt_path_version,
        )

        stage_started = time.monotonic()
        prompt_content = build_story_prompt(theme, prompt_path_version)
        _capture_stage_duration(stage_timings, "prompt_build", stage_started)
        generation_artifact["story_generation"]["prompt_full_text"] = prompt_content

        # Get the book response
        text_generator = build_text_generator()
        stage_started = time.monotonic()
        metadata_method = getattr(
            text_generator, "generate_book_response_with_metadata", None
        )
        if inspect.iscoroutinefunction(metadata_method):
            text_result_raw = await metadata_method(prompt_content)
        else:
            text_result_raw = await text_generator.generate_book_response(prompt_content)
        text_result = _to_text_generation_result(
            text_result_raw,
            provider=settings.text_provider,
            model={
                "openai": settings.openai_text_model,
                "google": settings.google_text_model,
            }.get(settings.text_provider, ""),
        )
        _capture_stage_duration(stage_timings, "text_generation", stage_started)
        assistant_message = text_result.content
        generation_artifact["story_generation"]["response_raw_json"] = assistant_message
        generation_artifact["story_generation"]["text_provider"] = text_result.provider
        generation_artifact["story_generation"]["text_model"] = text_result.model
        generation_artifact["story_generation"]["response_id"] = text_result.metadata.get(
            "response_id"
        )
        generation_artifact["story_generation"]["usage"] = text_result.metadata.get(
            "usage"
        )
        generation_artifact["story_generation"]["latency_seconds"] = (
            text_result.metadata.get("latency_seconds")
        )

        # Parse the assistant's message into a Book object
        stage_started = time.monotonic()
        try:
            book_data = json.loads(assistant_message)
            book = Book(**book_data)
            validate_book_for_prompt_path(book, prompt_path_version)
            generation_artifact["story_generation"]["parse_status"] = "success"
            book_id_str = str(book.book_id)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            generation_artifact["story_generation"]["parse_status"] = "json_decode_error"
            raise
        except Exception as e:
            logger.error(f"Error parsing book data: {e}")
            generation_artifact["story_generation"]["parse_status"] = (
                f"validation_error:{type(e).__name__}"
            )
            raise
        finally:
            _capture_stage_duration(stage_timings, "json_parse_and_validation", stage_started)

        progress.mark_work_completed(1.0, note="Story content generated.")

        # Assign relationships
        assign_book_model_relationships(book)

        # Set illustration style
        style_attributes = random.choice(pt.ILLUSTRATION_STYLE_ATTRIBUTES)
        book.illustration_style = style_attributes

        # One work unit per page illustration plus one for persisting book JSON.
        progress.set_stage("generating_illustrations")
        progress.add_total_work(float(len(book.pages) + 1))

        # Generate illustrations after creating the book
        image_artifact_context: Dict[str, Any] = {}
        stage_started = time.monotonic()
        illustrations = await generate_illustrations(
            book,
            progress,
            prompt_path_version=prompt_path_version,
            artifact_context=image_artifact_context,
        )
        _capture_stage_duration(stage_timings, "illustration_generation", stage_started)
        generation_artifact["image_generation"]["duration_seconds"] = stage_timings.get(
            "illustration_generation"
        )
        generation_artifact["image_generation"]["strategy"] = image_artifact_context.get(
            "strategy", settings.image_generation_strategy
        )
        generation_artifact["image_generation"]["page_count"] = image_artifact_context.get(
            "page_count", len(illustrations)
        )
        generation_artifact["image_generation"]["pages"] = image_artifact_context.get(
            "page_results", []
        )

        expiration_time = timedelta(hours=1)
        expires_at = datetime.now(timezone.utc) + expiration_time

        for page_number, image_data in illustrations.items():
            page = next((p for p in book.pages if p.page_number == page_number), None)
            if page:
                if settings.use_cloud_storage:
                    image_path = f"{book.book_id}/images/{page_number}.png"
                    url = generate_presigned_url(image_path, expiration=3600)
                else:
                    url = str(
                        (
                            Path(settings.local_data_path)
                            / f"{book.book_id}/images/{page_number}.png"
                        ).resolve()
                    )

                # Update illustration with URL and expiration metadata
                page.content.illustration = {
                    "url": url,
                    "expires_at": expires_at,
                }

        progress.set_stage("persisting_book_data")
        stage_started = time.monotonic()
        book_dir = construct_storage_path(book_id_str)
        if not settings.use_cloud_storage:
            ensure_directory_exists(book_dir)
        book_copy_no_refs = remove_book_model_relationships(book.copy(deep=True))
        book_data = book_copy_no_refs.dict()
        write_json_file(
            file_name=f"{book_id_str}.json",
            data=book_data,
            relative_path=book_dir,
            metadata={
                "artifact_type": "book_json",
                "book_id": book_id_str,
                "book_title": book.book_title,
                "prompt_path_version": prompt_path_version,
            },
        )
        _capture_stage_duration(stage_timings, "book_json_persist", stage_started)
        progress.mark_work_completed(1.0, note="Book JSON persisted.")

        usage = generation_artifact["story_generation"].get("usage") or {}
        generation_artifact["cost_analytics"]["text_prompt_tokens"] = usage.get(
            "prompt_tokens"
        )
        generation_artifact["cost_analytics"]["text_completion_tokens"] = usage.get(
            "completion_tokens"
        )
        generation_artifact["cost_analytics"]["text_total_tokens"] = usage.get(
            "total_tokens"
        )
        generation_artifact["cost_analytics"]["image_count_requested"] = len(book.pages)
        generation_artifact["cost_analytics"]["image_count_generated"] = len(
            generation_artifact["image_generation"]["pages"]
        )

        success = True
        return book
    except ValueError as e:
        failure_error = e
        if "content_policy_violation" in str(e):
            raise
        else:
            raise
    except Exception as e:
        failure_error = e
        raise
    finally:
        generation_artifact["timing"]["stages"] = stage_timings
        generation_artifact["run"]["status"] = "success" if success else "failed"
        generation_artifact["run"]["finished_at"] = _utcnow_iso()
        generation_artifact["run"]["total_duration_seconds"] = round(
            time.monotonic() - started_at, 3
        )
        if not success:
            generation_artifact["run"]["error"] = {
                "error_type": type(failure_error).__name__
                if failure_error is not None
                else "GenerationFailed",
                "error_message": str(failure_error) if failure_error is not None else None,
            }
            if not generation_artifact["image_generation"]["pages"]:
                partial_pages = _extract_partial_image_page_data(book)
                generation_artifact["image_generation"]["pages"] = partial_pages
                generation_artifact["image_generation"]["page_count"] = len(partial_pages)
        try:
            persist_started = time.monotonic()
            _persist_generation_artifact(
                generation_artifact,
                request_id=request_id,
                book_id=book_id_str,
            )
            _capture_stage_duration(stage_timings, "generation_artifact_persist", persist_started)
        except Exception as artifact_exc:
            logger.exception(
                "Failed to persist generation artifact. request_id=%s book_id=%s error=%s",
                request_id,
                book_id_str,
                str(artifact_exc),
            )
        await progress.stop(success=success)


async def generate_illustrations(
    book: Book,
    progress: GenerationProgressEstimator,
    prompt_path_version: str,
    artifact_context: Optional[Dict[str, Any]] = None,
) -> Dict[int, Any]:

    illustrations = await generate_page_illustrations(
        book,
        progress,
        prompt_path_version=prompt_path_version,
        artifact_context=artifact_context,
    )
    return illustrations


if __name__ == "__main__":
    # theme = "An adventure story about a 2 year old girl named June."
    # master_prompt = pt.PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS.format(theme=theme)
    # output_example = pt.TEMPLATE_CHILDRENS_BOOK
    # prompt_content = f"{master_prompt}\n{output_example}"
    # print(prompt_content)
    book_str = """
{
  "book_title": "The Blue Stripe Mystery",
  "book_length_n_pages": 10,
  "characters": [
    {
      "name": "June",
      "description": "A curious and happy toddler who loves to explore.",
      "appearance": "Short curly brown hair, yellow sun hat, red overalls, and white sneakers."
    },
    {
      "name": "Pip",
      "description": "A playful and energetic small puppy.",
      "appearance": "White fur, one black ear, a blue collar, and a wagging tail."
    }
  ],
  "settings": [
    {
      "id": "S1",
      "name": "Sunny Kitchen",
      "visual_anchor_details": "Bright morning light, checkered floor, wooden table, and a green rug."
    },
    {
      "id": "S2",
      "name": "Green Garden",
      "visual_anchor_details": "Soft green grass, pink flowers, a low wooden fence, and blue sky."
    },
    {
      "id": "S3",
      "name": "Cozy Nook",
      "visual_anchor_details": "Warm lamp light, soft striped blanket, a big pillow, and a toy box."
    }
  ],
  "plot_synopsis": "June finds a mysterious blue stripe on the kitchen floor. She follows the trail through the garden with her puppy, Pip. They discover the stripe is actually Pip's long leash. June chooses to follow it all the way back to their cozy nook for a nap.",
  "pages": [
    {
      "page_number": 1,
      "setting_id": "S1",
      "content": {
        "text_content_of_this_page": "June sees a bright blue stripe on the floor. Where does it go?",
        "illustration": "Wide shot. June wears her yellow sun hat and red overalls. She points at a blue ribbon on the checkered kitchen floor. She looks curious.",
        "characters_in_this_page": [
          "June"
        ]
      }
    },
    {
      "page_number": 2,
      "setting_id": "S1",
      "content": {
        "text_content_of_this_page": "June walks slow. She follows the blue stripe.",
        "illustration": "Medium shot. June crawls on the checkered floor next to the wooden table. She is smiling and focused. The blue line leads toward a door.",
        "characters_in_this_page": [
          "June"
        ]
      }
    },
    {
      "page_number": 3,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "The stripe goes out to the grass. June goes outside too.",
        "illustration": "Wide shot. June steps onto the soft green grass. The blue stripe winds past pink flowers under the blue sky. June looks excited.",
        "characters_in_this_page": [
          "June"
        ]
      }
    },
    {
      "page_number": 4,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "Look at that! June follows the blue stripe.",
        "illustration": "Medium shot. June is near the low wooden fence. She is bending over to touch the blue stripe in the grass. Her brown curls peek out from her hat.",
        "characters_in_this_page": [
          "June"
        ]
      }
    },
    {
      "page_number": 5,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "Pip wags his tail. He has the blue stripe!",
        "illustration": "Medium shot. Pip the puppy stands by the pink flowers. His blue collar is attached to the blue stripe. He looks happy and ready to play.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 6,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "Pip runs fast. June runs fast too.",
        "illustration": "Wide shot. Pip runs across the green grass with the blue line trailing behind. June chases him in her white sneakers, laughing loudly.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 7,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "Look at that! June follows the blue stripe.",
        "illustration": "Medium shot. Pip is hiding behind a large flower pot. June is peeking around the corner of the fence with a big grin.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 8,
      "setting_id": "S3",
      "content": {
        "text_content_of_this_page": "The sun goes down. June chooses to go inside.",
        "illustration": "Wide shot. June leads Pip by his blue stripe into the cozy nook. The warm lamp light glows. The toy box is open nearby.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 9,
      "setting_id": "S3",
      "content": {
        "text_content_of_this_page": "Look at that! June follows the blue stripe.",
        "illustration": "Close-up. June and Pip are on the striped blanket. June is taking off her yellow sun hat. They both look very sleepy and calm.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 10,
      "setting_id": "S3",
      "content": {
        "text_content_of_this_page": "June and Pip nap. The blue stripe stays still.",
        "illustration": "Medium shot. June is curled up on a big pillow with Pip. The blue stripe is coiled like a snake on the blanket. Everything is quiet.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    }
  ]
}
"""
    book_data = json.loads(book_str)
    book = Book(**book_data)
    print(book)
