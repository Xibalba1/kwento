#!/usr/bin/env python3
"""
Audit GCS book JSON artifacts against the current Pydantic book model.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set
from urllib.parse import unquote, urlparse

from pydantic import ValidationError


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
from utils.general_utils import get_gcs_client, read_json_file, write_json_file  # noqa: E402


CSV_COLUMNS = [
    "book_id",
    "blob_name",
    "error_stage",
    "error_type",
    "error_message",
    "validation_errors_json",
    "repair_attempted",
    "repair_applied",
    "repair_write_succeeded",
    "repair_count",
]


@dataclass
class ComplianceStats:
    scanned_books: int = 0
    compliant_books: int = 0
    non_compliant_books: int = 0
    skipped_missing_json: int = 0
    repair_attempted_books: int = 0
    repaired_books: int = 0
    repair_write_succeeded: int = 0


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
    stats: Optional[ComplianceStats] = None,
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


def _default_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        _backend_root()
        / "scripts"
        / "script_outputs"
        / f"gcs_book_json_compliance_{timestamp}.csv"
    )


def _validation_errors_json(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        try:
            return json.dumps(exc.errors(), sort_keys=True)
        except Exception:
            return "[]"
    return ""


def _failure_row(book_id: str, blob_name: str, stage: str, exc: Exception) -> Dict[str, str]:
    return {
        "book_id": book_id,
        "blob_name": blob_name,
        "error_stage": stage,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "validation_errors_json": _validation_errors_json(exc),
        "repair_attempted": "false",
        "repair_applied": "false",
        "repair_write_succeeded": "false",
        "repair_count": "0",
    }


def _repair_failure_row(
    *,
    book_id: str,
    blob_name: str,
    error_stage: str,
    exc: Exception,
    repair_attempted: bool,
    repair_applied: bool,
    repair_write_succeeded: bool,
    repair_count: int,
) -> Dict[str, str]:
    row = _failure_row(book_id, blob_name, error_stage, exc)
    row.update(
        {
            "repair_attempted": str(repair_attempted).lower(),
            "repair_applied": str(repair_applied).lower(),
            "repair_write_succeeded": str(repair_write_succeeded).lower(),
            "repair_count": str(repair_count),
        }
    )
    return row


def _repair_success_row(book_id: str, blob_name: str, repair_count: int) -> Dict[str, str]:
    return {
        "book_id": book_id,
        "blob_name": blob_name,
        "error_stage": "",
        "error_type": "",
        "error_message": "",
        "validation_errors_json": "",
        "repair_attempted": "true",
        "repair_applied": "true",
        "repair_write_succeeded": "true",
        "repair_count": str(repair_count),
    }


def _load_book_json(book_id: str) -> Dict[str, Any]:
    return read_json_file(file_name=f"{book_id}.json", relative_path=book_id)


def _validate_book_data(book_data: Dict[str, Any]) -> None:
    book = Book(**book_data)
    assign_book_model_relationships(book)


def _normalize_gcs_illustration_value(value: Any) -> Optional[str]:
    candidate = value
    if isinstance(value, dict):
        candidate = value.get("url")

    if not isinstance(candidate, str) or not candidate:
        return None

    if "?" not in candidate and not candidate.startswith("http"):
        return candidate

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return None

    bucket_name = settings.gcs_bucket_name
    if not bucket_name:
        return None

    path = parsed.path.strip("/")
    if parsed.netloc == "storage.googleapis.com":
        prefix = f"{bucket_name}/"
        if path.startswith(prefix):
            return path[len(prefix) :]
        download_prefix = f"download/storage/v1/b/{bucket_name}/o/"
        if path.startswith(download_prefix):
            return unquote(path[len(download_prefix) :])

    return None


def _canonicalize_illustration_values(book_data: Dict[str, Any]) -> int:
    normalized_count = 0
    for page in book_data.get("pages", []):
        if not isinstance(page, dict):
            continue
        content = page.get("content")
        if not isinstance(content, dict):
            continue
        illustration = content.get("illustration")
        normalized = _normalize_gcs_illustration_value(illustration)
        if normalized is None or normalized == illustration:
            continue
        content["illustration"] = normalized
        normalized_count += 1
    return normalized_count


def _book_json_metadata(book_data: Dict[str, Any]) -> Dict[str, str]:
    metadata = {
        "artifact_type": "book_json",
        "book_id": str(book_data.get("book_id", "")),
    }
    title = book_data.get("book_title")
    if isinstance(title, str) and title:
        metadata["book_title"] = title
    return metadata


def _write_repaired_book_json(book_id: str, book_data: Dict[str, Any]) -> str:
    return write_json_file(
        file_name=f"{book_id}.json",
        data=book_data,
        relative_path=book_id,
        metadata=_book_json_metadata(book_data),
    )


def _repair_status(repair_enabled: bool) -> str:
    return "ENABLED" if repair_enabled else "DISABLED"


def audit_gcs_book_json_compliance(
    *,
    output_csv: Path,
    requested_book_ids: Optional[Sequence[str]] = None,
    prefix: Optional[str] = None,
    limit: Optional[int] = None,
    repair: bool = False,
) -> ComplianceStats:
    if not settings.use_cloud_storage:
        raise ValueError("This script requires settings.use_cloud_storage=True.")
    if not settings.gcs_bucket_name:
        raise ValueError("GCS bucket name is not configured.")

    client = get_gcs_client()
    bucket = client.bucket(settings.gcs_bucket_name)
    stats = ComplianceStats()
    stage_counts: Counter[str] = Counter()
    candidate_ids = discover_candidate_book_ids(
        bucket,
        prefix=prefix,
        requested_book_ids=requested_book_ids,
        limit=limit,
        stats=stats,
    )

    output_csv.parent.mkdir(parents=True, exist_ok=True)

    print(f"Bucket: {settings.gcs_bucket_name}")
    print(f"Repair mode: {_repair_status(repair)}")
    print(f"Candidate books: {len(candidate_ids)}")
    print(f"CSV output: {output_csv}")

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for idx, book_id in enumerate(candidate_ids, start=1):
            stats.scanned_books += 1
            blob_name = f"{book_id}/{book_id}.json"
            book_data = _load_book_json(book_id)
            repair_attempted = False
            repair_applied = False
            repair_write_succeeded = False
            repair_count = 0

            try:
                _validate_book_data(book_data)
            except ValidationError as exc:
                stage = "model_validation"

                if repair:
                    stats.repair_attempted_books += 1
                    repair_attempted = True
                    repaired_book_data = copy.deepcopy(book_data)
                    repair_count = _canonicalize_illustration_values(repaired_book_data)
                    repair_applied = repair_count > 0

                    if repair_applied:
                        try:
                            _validate_book_data(repaired_book_data)
                            _write_repaired_book_json(book_id, repaired_book_data)
                            stats.repaired_books += 1
                            stats.repair_write_succeeded += 1
                            repair_write_succeeded = True
                            writer.writerow(
                                _repair_success_row(book_id, blob_name, repair_count)
                            )
                            print(
                                f"[{idx}/{len(candidate_ids)}] {book_id}: repaired "
                                f"({repair_count} illustration field(s) rewritten)"
                            )
                            continue
                        except ValidationError as repair_exc:
                            exc = repair_exc
                            stage = "model_validation"
                        except Exception as repair_exc:
                            exc = repair_exc
                            stage = "relationship_assignment"

                stats.non_compliant_books += 1
                stage_counts[stage] += 1
                writer.writerow(
                    _repair_failure_row(
                        book_id=book_id,
                        blob_name=blob_name,
                        error_stage=stage,
                        exc=exc,
                        repair_attempted=repair_attempted,
                        repair_applied=repair_applied,
                        repair_write_succeeded=repair_write_succeeded,
                        repair_count=repair_count,
                    )
                )
                print(
                    f"[{idx}/{len(candidate_ids)}] {book_id}: non-compliant "
                    f"({stage}: {type(exc).__name__})"
                )
                continue
            except Exception as exc:
                stats.non_compliant_books += 1
                stage_counts["relationship_assignment"] += 1
                writer.writerow(
                    _repair_failure_row(
                        book_id=book_id,
                        blob_name=blob_name,
                        error_stage="relationship_assignment",
                        exc=exc,
                        repair_attempted=False,
                        repair_applied=False,
                        repair_write_succeeded=False,
                        repair_count=0,
                    )
                )
                print(
                    f"[{idx}/{len(candidate_ids)}] {book_id}: non-compliant "
                    f"(relationship_assignment: {type(exc).__name__})"
                )
                continue

            if repair:
                stats.repair_attempted_books += 1
                repair_attempted = True
                repaired_book_data = copy.deepcopy(book_data)
                repair_count = _canonicalize_illustration_values(repaired_book_data)
                repair_applied = repair_count > 0

                if repair_applied:
                    try:
                        _validate_book_data(repaired_book_data)
                        _write_repaired_book_json(book_id, repaired_book_data)
                        stats.repaired_books += 1
                        stats.repair_write_succeeded += 1
                        repair_write_succeeded = True
                        writer.writerow(
                            _repair_success_row(book_id, blob_name, repair_count)
                        )
                        print(
                            f"[{idx}/{len(candidate_ids)}] {book_id}: repaired "
                            f"({repair_count} illustration field(s) normalized)"
                        )
                        continue
                    except ValidationError as exc:
                        stats.non_compliant_books += 1
                        stage_counts["model_validation"] += 1
                        writer.writerow(
                            _repair_failure_row(
                                book_id=book_id,
                                blob_name=blob_name,
                                error_stage="model_validation",
                                exc=exc,
                                repair_attempted=repair_attempted,
                                repair_applied=repair_applied,
                                repair_write_succeeded=repair_write_succeeded,
                                repair_count=repair_count,
                            )
                        )
                        print(
                            f"[{idx}/{len(candidate_ids)}] {book_id}: non-compliant "
                            f"(model_validation: {type(exc).__name__})"
                        )
                        continue
                    except Exception as exc:
                        stats.non_compliant_books += 1
                        stage_counts["relationship_assignment"] += 1
                        writer.writerow(
                            _repair_failure_row(
                                book_id=book_id,
                                blob_name=blob_name,
                                error_stage="relationship_assignment",
                                exc=exc,
                                repair_attempted=repair_attempted,
                                repair_applied=repair_applied,
                                repair_write_succeeded=repair_write_succeeded,
                                repair_count=repair_count,
                            )
                        )
                        print(
                            f"[{idx}/{len(candidate_ids)}] {book_id}: non-compliant "
                            f"(relationship_assignment: {type(exc).__name__})"
                        )
                        continue

            stats.compliant_books += 1
            print(f"[{idx}/{len(candidate_ids)}] {book_id}: compliant")

    print("\nSummary")
    print(f"- scanned_books: {stats.scanned_books}")
    print(f"- compliant_books: {stats.compliant_books}")
    print(f"- non_compliant_books: {stats.non_compliant_books}")
    print(f"- skipped_missing_json: {stats.skipped_missing_json}")
    print(f"- repair_attempted_books: {stats.repair_attempted_books}")
    print(f"- repaired_books: {stats.repaired_books}")
    print(f"- repair_write_succeeded: {stats.repair_write_succeeded}")
    if stage_counts:
        print("- non_compliant_by_stage:")
        for stage, count in sorted(stage_counts.items()):
            print(f"  - {stage}: {count}")

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit GCS book JSON artifacts against the current Book model."
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
        "--output",
        default=str(_default_output_path()),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Attempt the narrow illustration-object to URL-string repair and write only fully valid repaired blobs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    audit_gcs_book_json_compliance(
        output_csv=output,
        requested_book_ids=args.book_id,
        prefix=args.prefix,
        limit=args.limit,
        repair=args.repair,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
