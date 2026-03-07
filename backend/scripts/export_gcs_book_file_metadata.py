#!/usr/bin/env python3
"""
Export Google Cloud Storage object metadata for the books bucket to CSV.

One CSV row = one blob/object (json, image, etc.).

Usage:
  python backend/scripts/export_gcs_book_file_metadata.py
  python backend/scripts/export_gcs_book_file_metadata.py --bucket kwento-books
  python backend/scripts/export_gcs_book_file_metadata.py --prefix "<book_id>/" --output ./out.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _wire_import_path() -> None:
    backend_root = _backend_root()
    src_path = backend_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


_wire_import_path()

from config import settings  # noqa: E402
from utils.general_utils import get_gcs_client, get_gcs_file_url  # noqa: E402


CSV_COLUMNS = [
    "bucket_name",
    "blob_name",
    "gcs_uri",
    "public_url",
    "top_level_dir",
    "parent_dir",
    "file_name",
    "file_extension",
    "inferred_book_id",
    "inferred_file_kind",
    "inferred_page_number",
    "metadata_book_id",
    "metadata_book_title",
    "metadata_json",
    "size_bytes",
    "content_type",
    "content_language",
    "content_encoding",
    "cache_control",
    "content_disposition",
    "storage_class",
    "time_created",
    "updated",
    "time_deleted",
    "retention_expiration_time",
    "custom_time",
    "temporary_hold",
    "event_based_hold",
    "generation",
    "metageneration",
    "etag",
    "crc32c",
    "md5_hash",
    "kms_key_name",
    "component_count",
    "self_link",
    "media_link",
]


@dataclass
class ExportStats:
    blob_count: int = 0


def _dt_to_iso(value: Optional[datetime]) -> str:
    if not value:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value or {}, sort_keys=True)
    except Exception:
        return "{}"


def _split_blob_path(blob_name: str) -> Dict[str, str]:
    path = blob_name.strip("/")
    parts = [part for part in path.split("/") if part]

    top_level = parts[0] if len(parts) >= 1 else ""
    file_name = parts[-1] if len(parts) >= 1 else ""
    parent = "/".join(parts[:-1]) if len(parts) >= 2 else ""
    ext = Path(file_name).suffix.lower().lstrip(".") if file_name else ""

    return {
        "top_level_dir": top_level,
        "parent_dir": parent,
        "file_name": file_name,
        "file_extension": ext,
    }


def _infer_book_shape(blob_name: str) -> Dict[str, str]:
    parts = [part for part in blob_name.strip("/").split("/") if part]

    inferred_book_id = parts[0] if parts else ""
    inferred_file_kind = "other"
    inferred_page_number = ""

    if blob_name.endswith(".json"):
        inferred_file_kind = "book_json"
    elif len(parts) >= 3 and parts[1] == "images" and parts[-1].endswith(".png"):
        inferred_file_kind = "image"
        page_str = parts[-1].replace(".png", "")
        if page_str.isdigit():
            inferred_page_number = page_str

    return {
        "inferred_book_id": inferred_book_id,
        "inferred_file_kind": inferred_file_kind,
        "inferred_page_number": inferred_page_number,
    }


def _blob_to_row(bucket_name: str, blob: Any) -> Dict[str, Any]:
    blob.reload()
    metadata = blob.metadata or {}

    split_fields = _split_blob_path(blob.name)
    inferred_fields = _infer_book_shape(blob.name)

    row = {
        "bucket_name": bucket_name,
        "blob_name": blob.name,
        "gcs_uri": f"gs://{bucket_name}/{blob.name}",
        "public_url": get_gcs_file_url(blob.name),
        "metadata_book_id": metadata.get("book_id", ""),
        "metadata_book_title": metadata.get("book_title", ""),
        "metadata_json": _safe_json(metadata),
        "size_bytes": blob.size if blob.size is not None else "",
        "content_type": blob.content_type or "",
        "content_language": blob.content_language or "",
        "content_encoding": blob.content_encoding or "",
        "cache_control": blob.cache_control or "",
        "content_disposition": blob.content_disposition or "",
        "storage_class": blob.storage_class or "",
        "time_created": _dt_to_iso(blob.time_created),
        "updated": _dt_to_iso(blob.updated),
        "time_deleted": _dt_to_iso(blob.time_deleted),
        "retention_expiration_time": _dt_to_iso(blob.retention_expiration_time),
        "custom_time": _dt_to_iso(blob.custom_time),
        "temporary_hold": bool(blob.temporary_hold)
        if blob.temporary_hold is not None
        else "",
        "event_based_hold": bool(blob.event_based_hold)
        if blob.event_based_hold is not None
        else "",
        "generation": blob.generation or "",
        "metageneration": blob.metageneration or "",
        "etag": blob.etag or "",
        "crc32c": blob.crc32c or "",
        "md5_hash": blob.md5_hash or "",
        "kms_key_name": blob.kms_key_name or "",
        "component_count": blob.component_count or "",
        "self_link": blob.self_link or "",
        "media_link": blob.media_link or "",
    }

    row.update(split_fields)
    row.update(inferred_fields)
    return row


def export_bucket_metadata_to_csv(
    output_csv: Path,
    bucket_name: Optional[str] = None,
    prefix: Optional[str] = None,
    include_non_book_paths: bool = True,
) -> ExportStats:
    selected_bucket = bucket_name or settings.gcs_bucket_name
    if not selected_bucket:
        raise ValueError("GCS bucket name is not configured.")

    client = get_gcs_client()
    bucket = client.bucket(selected_bucket)
    blobs = bucket.list_blobs(prefix=prefix)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    stats = ExportStats()

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for blob in blobs:
            if not include_non_book_paths:
                parts = [part for part in blob.name.strip("/").split("/") if part]
                if len(parts) < 2:
                    continue

            row = _blob_to_row(selected_bucket, blob)
            writer.writerow(row)
            stats.blob_count += 1

    return stats


def _default_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return _backend_root() / "scripts" / "script_outputs" / f"gcs_book_file_metadata_{timestamp}.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export GCS file metadata for bucket objects to a relational-style CSV."
    )
    parser.add_argument(
        "--bucket",
        default=None,
        help="GCS bucket name. Defaults to settings.gcs_bucket_name.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Optional GCS prefix filter (for example, '<book_id>/' or 'some/path/').",
    )
    parser.add_argument(
        "--output",
        default=str(_default_output_path()),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--only-book-like-paths",
        action="store_true",
        help="If set, skips shallow paths that do not resemble '<book_id>/<...>'.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()

    stats = export_bucket_metadata_to_csv(
        output_csv=output,
        bucket_name=args.bucket,
        prefix=args.prefix,
        include_non_book_paths=not args.only_book_like_paths,
    )

    print(f"Exported {stats.blob_count} blobs to CSV: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
