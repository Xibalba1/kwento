#!/usr/bin/env python3
# backend/scripts/resize_gcs_covers.py
"""
Resize oversized GCS cover.png files into thumbnail-sized PNGs.

Default mode is dry-run. Pass --execute to actually overwrite files in GCS.
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from PIL import Image


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _wire_import_path() -> None:
    backend_root = _backend_root()
    src_path = backend_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


_wire_import_path()

from backfill_missing_gcs_covers import discover_candidate_book_ids  # noqa: E402
from config import settings  # noqa: E402
from services.image_service import save_image  # noqa: E402
from utils.general_utils import get_gcs_client  # noqa: E402


DEFAULT_MAX_WIDTH = 320
DEFAULT_MAX_HEIGHT = 480


@dataclass
class ResizeStats:
    scanned_books: int = 0
    resized_books: int = 0
    skipped_missing_cover: int = 0
    skipped_already_small: int = 0
    skipped_not_smaller: int = 0
    failed_resize: int = 0


@dataclass
class ResizeResult:
    image_bytes: bytes
    original_width: int
    original_height: int
    resized_width: int
    resized_height: int


def _resize_cover_bytes(
    image_bytes: bytes, *, max_width: int, max_height: int
) -> ResizeResult:
    with Image.open(io.BytesIO(image_bytes)) as image:
        source = image.convert("RGBA") if image.mode not in ("RGB", "RGBA") else image.copy()
        original_width, original_height = source.size
        resized = source.copy()
        resized.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        resized_width, resized_height = resized.size

        output = io.BytesIO()
        resized.save(output, format="PNG", optimize=True, compress_level=9)
        return ResizeResult(
            image_bytes=output.getvalue(),
            original_width=original_width,
            original_height=original_height,
            resized_width=resized_width,
            resized_height=resized_height,
        )


def resize_gcs_covers(
    *,
    requested_book_ids: Optional[Sequence[str]] = None,
    prefix: Optional[str] = None,
    limit: Optional[int] = None,
    max_width: int = DEFAULT_MAX_WIDTH,
    max_height: int = DEFAULT_MAX_HEIGHT,
    execute: bool = False,
) -> ResizeStats:
    if max_width <= 0 or max_height <= 0:
        raise ValueError("Thumbnail dimensions must be positive integers.")
    if not settings.use_cloud_storage:
        raise ValueError("This script requires settings.use_cloud_storage=True.")
    if not settings.gcs_bucket_name:
        raise ValueError("GCS bucket name is not configured.")

    client = get_gcs_client()
    bucket = client.bucket(settings.gcs_bucket_name)
    stats = ResizeStats()
    candidate_ids = discover_candidate_book_ids(
        bucket,
        prefix=prefix,
        requested_book_ids=requested_book_ids,
        limit=limit,
    )

    print(f"Bucket: {settings.gcs_bucket_name}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY_RUN'}")
    print(f"Candidate books: {len(candidate_ids)}")
    print(f"Thumbnail box: {max_width}x{max_height}")

    for idx, book_id in enumerate(candidate_ids, start=1):
        stats.scanned_books += 1
        cover_blob = bucket.blob(f"{book_id}/cover.png")
        if not cover_blob.exists():
            stats.skipped_missing_cover += 1
            print(f"[{idx}/{len(candidate_ids)}] {book_id}: missing cover.png")
            continue

        try:
            original_bytes = cover_blob.download_as_bytes()
            resize_result = _resize_cover_bytes(
                original_bytes,
                max_width=max_width,
                max_height=max_height,
            )
        except Exception as exc:
            stats.failed_resize += 1
            print(
                f"[{idx}/{len(candidate_ids)}] {book_id}: failed "
                f"({type(exc).__name__}: {exc})"
            )
            continue

        size_changed = (
            resize_result.resized_width != resize_result.original_width
            or resize_result.resized_height != resize_result.original_height
        )
        smaller_bytes = len(resize_result.image_bytes) < len(original_bytes)

        if not size_changed:
            stats.skipped_already_small += 1
            print(
                f"[{idx}/{len(candidate_ids)}] {book_id}: already within target "
                f"({resize_result.original_width}x{resize_result.original_height}, "
                f"{len(original_bytes)} B)"
            )
            continue

        if not smaller_bytes:
            stats.skipped_not_smaller += 1
            print(
                f"[{idx}/{len(candidate_ids)}] {book_id}: resized dimensions "
                f"{resize_result.original_width}x{resize_result.original_height} -> "
                f"{resize_result.resized_width}x{resize_result.resized_height}, "
                f"but bytes did not shrink ({len(original_bytes)} B -> "
                f"{len(resize_result.image_bytes)} B)"
            )
            continue

        if not execute:
            print(
                f"[{idx}/{len(candidate_ids)}] {book_id}: would overwrite cover.png "
                f"{resize_result.original_width}x{resize_result.original_height} -> "
                f"{resize_result.resized_width}x{resize_result.resized_height}, "
                f"{len(original_bytes)} B -> {len(resize_result.image_bytes)} B"
            )
            continue

        try:
            saved_path = save_image(resize_result.image_bytes, f"{book_id}/cover.png")
            stats.resized_books += 1
            print(
                f"[{idx}/{len(candidate_ids)}] {book_id}: overwrote {saved_path} "
                f"{resize_result.original_width}x{resize_result.original_height} -> "
                f"{resize_result.resized_width}x{resize_result.resized_height}, "
                f"{len(original_bytes)} B -> {len(resize_result.image_bytes)} B"
            )
        except Exception as exc:
            stats.failed_resize += 1
            print(
                f"[{idx}/{len(candidate_ids)}] {book_id}: upload failed "
                f"({type(exc).__name__}: {exc})"
            )

    print("\nSummary")
    print(f"- scanned_books: {stats.scanned_books}")
    print(f"- resized_books: {stats.resized_books}")
    print(f"- skipped_missing_cover: {stats.skipped_missing_cover}")
    print(f"- skipped_already_small: {stats.skipped_already_small}")
    print(f"- skipped_not_smaller: {stats.skipped_not_smaller}")
    print(f"- failed_resize: {stats.failed_resize}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resize GCS cover.png files to thumbnail dimensions."
    )
    parser.add_argument(
        "--book-id",
        action="append",
        default=[],
        help="Specific book ID to process. Repeat for multiple IDs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of candidate books to process.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Optional GCS prefix filter used during discovery.",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=DEFAULT_MAX_WIDTH,
        help=f"Maximum thumbnail width in pixels. Default: {DEFAULT_MAX_WIDTH}.",
    )
    parser.add_argument(
        "--max-height",
        type=int,
        default=DEFAULT_MAX_HEIGHT,
        help=f"Maximum thumbnail height in pixels. Default: {DEFAULT_MAX_HEIGHT}.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually overwrite cover.png files in GCS. Without this flag, runs as dry-run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    resize_gcs_covers(
        requested_book_ids=args.book_id,
        prefix=args.prefix,
        limit=args.limit,
        max_width=args.max_width,
        max_height=args.max_height,
        execute=args.execute,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
