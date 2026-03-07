#!/usr/bin/env python3
"""
Delete books from GCS by book ID.

Each book is assumed to live under a top-level prefix named exactly as the book ID:
  <book_id>/...

Update BOOK_IDS_TO_DELETE below, then run with Poetry.
By default this script runs in DRY_RUN mode.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


# Paste book IDs here.
BOOK_IDS_TO_DELETE: List[str] = [
    "3498fa3e-35f3-4021-b0a1-6c75b1b0e549",
    "87702bb8-ce10-42bf-9c9e-a6914d2ba0b9",
    "d3af7fa6-fd61-407e-a325-2fc42b6695cd",
    "d54a7b10-092e-4092-af18-1022c8ed33a3",
    "df9378c4-7cc4-407b-9ce8-8ceb14e14296",
    "09c4b243-358c-406f-b448-94ae509e3908",
    "0d461692-6008-4d82-8f9e-ef996f71810f",
    "21e0fe1a-693b-47dd-b1a6-841b3388ff2d",
    "c8811383-24aa-46ca-9e49-2b7d9595cfad",
    "e460f93c-c464-4844-88bb-643ff10a2884",
    "f4a0d3f4-d34f-4d37-a58a-3b4b71ee0a54",
    "f855a054-0d1e-4abb-832b-20b24297af63",
    "8c754331-ce8c-4d06-a8fb-13d5c4a8e540",
    "d0c127d1-821c-4ae2-9d1b-ec43044af363",
    "7944407d-599d-4188-9e61-9c01a6874dbd",
    "58fdfe58-41c0-49f9-8ffd-dc44db8951a1",
    "19aec267-430b-4dd5-9dc2-322a102ea01b",
    "024ab216-48c6-4a85-9457-1f124797f4b5",
    "044bc45e-c08c-4347-8b06-d8202c8b5886",
    "255b8dcb-5568-4ba1-bc8c-abbe8d453f2a",
    "2c053280-8c51-44b9-bfa7-cc1ed9d882a1",
    "31c2f275-3e92-4e82-ac6b-bbb28a04a37f",
    "3428efdb-86f5-4ef2-9c5c-e39dcd9d9091",
    "5a62a3e6-04ea-4abd-97c3-6035f4e825a2",
    "7fca78b0-8857-43fc-8def-a142281a425d",
    "427b07e9-3f53-4244-9a69-8914a64090b9",
    "61c4cad6-537f-4db1-af84-648f14ca3cc0",
    "8b795cb2-9d50-499b-9fa2-a42cb64c30fb",
    "c111fec1-bed4-44ca-9633-cb1de85d3045",
    "62cc6c97-6fda-4675-ae47-e65dd27c69ae",
    "310710da-e2eb-4938-99f6-d48858e9263a",
    "3929b950-27c1-41e4-b436-997e51364457",
    "404e1a8c-d805-4d59-b3de-efc806892005",
    "ab813f48-7e2d-4b24-a65a-5b7d60c01dd1",
    "ef2ff58c-1e62-4fff-be11-0b5131a67e41",
    "feffaac6-5cf5-4ba9-bf94-bcf709b6d851",
]

# Safety switch. Keep True to preview deletions without deleting.
DRY_RUN = True


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _wire_import_path() -> None:
    backend_root = _backend_root()
    src_path = backend_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


_wire_import_path()

from config import settings  # noqa: E402
from utils.general_utils import get_gcs_client  # noqa: E402


@dataclass
class DeleteStats:
    requested_book_ids: int = 0
    matched_book_ids: int = 0
    deleted_objects: int = 0
    missing_book_ids: int = 0


def _normalize_book_ids(book_ids: Iterable[str]) -> List[str]:
    normalized = []
    for raw in book_ids:
        value = (raw or "").strip().strip("/")
        if value:
            normalized.append(value)

    # De-duplicate while preserving input order.
    seen = set()
    deduped = []
    for book_id in normalized:
        if book_id in seen:
            continue
        seen.add(book_id)
        deduped.append(book_id)
    return deduped


def _prefix_for_book(book_id: str) -> str:
    return f"{book_id}/"


def delete_books_from_bucket(book_ids: List[str], dry_run: bool = True) -> DeleteStats:
    bucket_name = settings.gcs_bucket_name
    if not bucket_name:
        raise ValueError("GCS bucket name is not configured.")

    client = get_gcs_client()
    bucket = client.bucket(bucket_name)

    ids = _normalize_book_ids(book_ids)
    stats = DeleteStats(requested_book_ids=len(ids))

    if not ids:
        print("No book IDs provided. Update BOOK_IDS_TO_DELETE in the script.")
        return stats

    print(f"Bucket: {bucket_name}")
    print(f"Mode: {'DRY_RUN (no deletes)' if dry_run else 'EXECUTE (deletes enabled)'}")
    print(f"Book IDs requested: {len(ids)}")

    for idx, book_id in enumerate(ids, start=1):
        prefix = _prefix_for_book(book_id)
        blobs = list(bucket.list_blobs(prefix=prefix))

        if not blobs:
            stats.missing_book_ids += 1
            print(
                f"[{idx}/{len(ids)}] {book_id}: no objects found under prefix '{prefix}'"
            )
            continue

        stats.matched_book_ids += 1
        object_count = len(blobs)
        print(
            f"[{idx}/{len(ids)}] {book_id}: found {object_count} object(s) under '{prefix}'"
        )

        if dry_run:
            preview = [blob.name for blob in blobs[:5]]
            for name in preview:
                print(f"  - {name}")
            if object_count > 5:
                print(f"  ... and {object_count - 5} more")
            continue

        deleted_for_book = 0
        for blob in blobs:
            blob.delete()
            deleted_for_book += 1

        stats.deleted_objects += deleted_for_book
        print(f"  deleted {deleted_for_book} object(s)")

    print("\nSummary")
    print(f"- requested_book_ids: {stats.requested_book_ids}")
    print(f"- matched_book_ids: {stats.matched_book_ids}")
    print(f"- missing_book_ids: {stats.missing_book_ids}")
    print(f"- deleted_objects: {stats.deleted_objects}")

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Delete all GCS objects under each <book_id>/ prefix for IDs in BOOK_IDS_TO_DELETE."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete objects. Without this flag, script runs as dry-run.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dry_run = DRY_RUN and not args.execute

    delete_books_from_bucket(BOOK_IDS_TO_DELETE, dry_run=dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
