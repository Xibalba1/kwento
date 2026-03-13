#!/usr/bin/env python3
# backend/scripts/backfill_missing_gcs_covers.py
"""
Backfill missing cover.png files for legacy books stored in GCS.

Default mode is dry-run. Pass --execute to actually generate and upload covers.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _wire_import_path() -> None:
    backend_root = _backend_root()
    src_path = backend_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


_wire_import_path()

from api.models.book_models import Book  # noqa: E402
from api.models.helpers import assign_book_model_relationships  # noqa: E402
from config import settings  # noqa: E402
from core.image_generation import generate_cover_from_reference  # noqa: E402
from utils.general_utils import get_gcs_client, read_json_file  # noqa: E402


@dataclass
class BackfillStats:
    scanned_books: int = 0
    already_had_cover: int = 0
    generated_cover: int = 0
    skipped_missing_json: int = 0
    skipped_missing_seed_page_image: int = 0
    failed_generation: int = 0


def _normalize_book_ids(book_ids: Optional[Iterable[str]]) -> List[str]:
    normalized: List[str] = []
    seen: Set[str] = set()
    for raw in book_ids or []:
        value = (raw or "").strip().strip("/")
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _discover_top_level_prefixes(bucket, prefix: Optional[str] = None) -> List[str]:
    normalized_prefix = (prefix or "").strip().strip("/")
    list_prefix = f"{normalized_prefix}/" if normalized_prefix else None
    top_levels: Set[str] = set()

    for blob in bucket.list_blobs(prefix=list_prefix):
        parts = [part for part in blob.name.strip("/").split("/") if part]
        if parts:
            top_levels.add(parts[0])

    return sorted(top_levels)


def discover_candidate_book_ids(
    bucket,
    *,
    prefix: Optional[str] = None,
    requested_book_ids: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    stats: Optional[BackfillStats] = None,
) -> List[str]:
    selected_ids = _normalize_book_ids(requested_book_ids)
    if selected_ids:
        candidate_ids = selected_ids
    else:
        candidate_ids = _discover_top_level_prefixes(bucket, prefix=prefix)

    valid_ids: List[str] = []
    for book_id in candidate_ids:
        json_blob = bucket.blob(f"{book_id}/{book_id}.json")
        if not json_blob.exists():
            if stats is not None:
                stats.skipped_missing_json += 1
            continue
        valid_ids.append(book_id)
        if limit is not None and len(valid_ids) >= limit:
            break

    return valid_ids


def _load_book(book_id: str) -> Book:
    book_data = read_json_file(file_name=f"{book_id}.json", relative_path=book_id)
    book = Book(**book_data)
    return assign_book_model_relationships(book)


def _download_seed_image_bytes(bucket, book_id: str) -> Optional[bytes]:
    seed_blob = bucket.blob(f"{book_id}/images/1.png")
    if not seed_blob.exists():
        return None
    return seed_blob.download_as_bytes()


async def _generate_cover(book: Book, reference_image_bytes: bytes) -> dict:
    return await generate_cover_from_reference(book, reference_image_bytes)


def backfill_missing_covers(
    *,
    requested_book_ids: Optional[Sequence[str]] = None,
    prefix: Optional[str] = None,
    limit: Optional[int] = None,
    execute: bool = False,
) -> BackfillStats:
    if not settings.use_cloud_storage:
        raise ValueError("This script requires settings.use_cloud_storage=True.")
    if not settings.gcs_bucket_name:
        raise ValueError("GCS bucket name is not configured.")

    client = get_gcs_client()
    bucket = client.bucket(settings.gcs_bucket_name)
    stats = BackfillStats()
    candidate_ids = discover_candidate_book_ids(
        bucket,
        prefix=prefix,
        requested_book_ids=requested_book_ids,
        limit=limit,
        stats=stats,
    )

    print(f"Bucket: {settings.gcs_bucket_name}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY_RUN'}")
    print(f"Candidate books: {len(candidate_ids)}")

    for idx, book_id in enumerate(candidate_ids, start=1):
        stats.scanned_books += 1
        cover_blob = bucket.blob(f"{book_id}/cover.png")
        if cover_blob.exists():
            stats.already_had_cover += 1
            print(f"[{idx}/{len(candidate_ids)}] {book_id}: cover already exists")
            continue

        seed_image_bytes = _download_seed_image_bytes(bucket, book_id)
        if seed_image_bytes is None:
            stats.skipped_missing_seed_page_image += 1
            print(f"[{idx}/{len(candidate_ids)}] {book_id}: missing images/1.png")
            continue

        if not execute:
            print(f"[{idx}/{len(candidate_ids)}] {book_id}: would generate cover")
            continue

        try:
            book = _load_book(book_id)
            result = asyncio.run(_generate_cover(book, seed_image_bytes))
            stats.generated_cover += 1
            print(
                f"[{idx}/{len(candidate_ids)}] {book_id}: generated {result.get('saved_path')}"
            )
        except Exception as exc:
            stats.failed_generation += 1
            print(
                f"[{idx}/{len(candidate_ids)}] {book_id}: failed ({type(exc).__name__}: {exc})"
            )

    print("\nSummary")
    print(f"- scanned_books: {stats.scanned_books}")
    print(f"- already_had_cover: {stats.already_had_cover}")
    print(f"- generated_cover: {stats.generated_cover}")
    print(f"- skipped_missing_json: {stats.skipped_missing_json}")
    print(
        "- skipped_missing_seed_page_image: " f"{stats.skipped_missing_seed_page_image}"
    )
    print(f"- failed_generation: {stats.failed_generation}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate missing cover.png files for legacy books in GCS."
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
        "--execute",
        action="store_true",
        help="Actually generate and upload covers. Without this flag, runs as dry-run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    backfill_missing_covers(
        requested_book_ids=args.book_id,
        prefix=args.prefix,
        limit=args.limit,
        execute=args.execute,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
