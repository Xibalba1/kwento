import csv
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from pydantic import ValidationError


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "audit_gcs_book_json_compliance.py"
    )
    spec = importlib.util.spec_from_file_location(
        "audit_gcs_book_json_compliance", script_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeBlob:
    def __init__(self, name, *, exists=True):
        self.name = name
        self._exists = exists

    def exists(self):
        return self._exists


class FakeBucket:
    def __init__(self, names, *, existing=None):
        self._list_blobs = [FakeBlob(name) for name in names]
        self._existing = existing or {}

    def list_blobs(self, prefix=None):
        if prefix is None:
            return list(self._list_blobs)
        return [blob for blob in self._list_blobs if blob.name.startswith(prefix)]

    def blob(self, name):
        return FakeBlob(name, exists=self._existing.get(name, False))


def _invalid_illustration_book(book_id="book-a"):
    return {
        "book_id": book_id,
        "book_title": "Title",
        "book_length_n_pages": 1,
        "characters": [],
        "settings": [],
        "plot_synopsis": "Plot",
        "pages": [
            {
                "page_number": 1,
                "content": {
                    "text_content_of_this_page": "Text",
                    "characters_in_this_page": [],
                    "illustration": {
                        "url": f"https://storage.googleapis.com/kwento-books/{book_id}/images/1.png",
                        "expires_at": "2026-03-12 02:34:23.579488+00:00",
                    },
                },
            }
        ],
        "illustration_style": {},
    }


def _signed_url(book_id="book-a", page_number=1):
    return (
        f"https://storage.googleapis.com/kwento-books/{book_id}/images/{page_number}.png"
        "?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Expires=3600"
    )


def test_discover_candidate_book_ids_skips_invalid_prefixes_and_limits():
    module = _load_script_module()
    stats = module.ComplianceStats()
    bucket = FakeBucket(
        [
            "book-a/book-a.json",
            "book-a/images/1.png",
            "book-b/images/1.png",
            "misc/file.txt",
        ],
        existing={
            "book-a/book-a.json": True,
            "book-b/book-b.json": False,
            "misc/misc.json": False,
        },
    )

    result = module.discover_candidate_book_ids(bucket, limit=1, stats=stats)

    assert result == ["book-a"]
    assert stats.skipped_missing_json == 2


def test_audit_marks_compliant_books_and_writes_header_only(monkeypatch, tmp_path):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={"book-a/book-a.json": True},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: {"ok": True})
    monkeypatch.setattr(module, "_validate_book_data", lambda book_data: None)

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(output_csv=output)

    assert stats.scanned_books == 1
    assert stats.compliant_books == 1
    assert stats.non_compliant_books == 0
    assert stats.repaired_books == 0

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert rows == []


def test_audit_reports_model_validation_failures_with_details(monkeypatch, tmp_path):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={"book-a/book-a.json": True},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: {"bad": True})

    def fail_validation(book_data):
        module.Book(book_title="Missing required fields")

    monkeypatch.setattr(module, "_validate_book_data", fail_validation)

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(output_csv=output)

    assert stats.scanned_books == 1
    assert stats.non_compliant_books == 1
    assert stats.compliant_books == 0

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["book_id"] == "book-a"
    assert rows[0]["error_stage"] == "model_validation"
    assert rows[0]["error_type"] == "ValidationError"
    assert rows[0]["validation_errors_json"]
    assert rows[0]["repair_attempted"] == "false"


def test_audit_reports_relationship_assignment_failures(monkeypatch, tmp_path):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={"book-a/book-a.json": True},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: {"ok": True})

    def fail_relationships(book_data):
        raise RuntimeError("bad relationship state")

    monkeypatch.setattr(module, "_validate_book_data", fail_relationships)

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(output_csv=output)

    assert stats.scanned_books == 1
    assert stats.non_compliant_books == 1

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["error_stage"] == "relationship_assignment"
    assert rows[0]["error_type"] == "RuntimeError"
    assert rows[0]["validation_errors_json"] == ""


def test_audit_repair_disabled_does_not_write(monkeypatch, tmp_path):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={"book-a/book-a.json": True},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)
    writes = []

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: _invalid_illustration_book(book_id))
    monkeypatch.setattr(module, "_write_repaired_book_json", lambda book_id, book_data: writes.append((book_id, book_data)))

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(output_csv=output, repair=False)

    assert stats.non_compliant_books == 1
    assert stats.repair_attempted_books == 0
    assert writes == []

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert rows[0]["repair_attempted"] == "false"
    assert rows[0]["repair_write_succeeded"] == "false"


def test_audit_repair_enabled_writes_only_after_validation(monkeypatch, tmp_path):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={"book-a/book-a.json": True},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)
    writes = []

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: _invalid_illustration_book(book_id))

    def validate(book_data):
        illustration = book_data["pages"][0]["content"]["illustration"]
        if isinstance(illustration, dict):
            raise ValidationError.from_exception_data(
                "Book",
                [
                    {
                        "type": "string_type",
                        "loc": ("pages", 0, "content", "illustration"),
                        "msg": "Input should be a valid string",
                        "input": illustration,
                    }
                ],
            )

    monkeypatch.setattr(module, "_validate_book_data", validate)
    monkeypatch.setattr(
        module,
        "_write_repaired_book_json",
        lambda book_id, book_data: writes.append((book_id, book_data)),
    )

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(output_csv=output, repair=True)

    assert stats.non_compliant_books == 0
    assert stats.repair_attempted_books == 1
    assert stats.repaired_books == 1
    assert stats.repair_write_succeeded == 1
    assert len(writes) == 1
    assert writes[0][0] == "book-a"
    assert (
        writes[0][1]["pages"][0]["content"]["illustration"] == "book-a/images/1.png"
    )

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["repair_attempted"] == "true"
    assert rows[0]["repair_applied"] == "true"
    assert rows[0]["repair_write_succeeded"] == "true"
    assert rows[0]["repair_count"] == "1"


def test_audit_repair_enabled_does_not_write_if_other_errors_remain(monkeypatch, tmp_path):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={"book-a/book-a.json": True},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)
    writes = []
    validation_calls = {"count": 0}

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: _invalid_illustration_book(book_id))

    def validate(book_data):
        validation_calls["count"] += 1
        illustration = book_data["pages"][0]["content"]["illustration"]
        if validation_calls["count"] == 1:
            raise ValidationError.from_exception_data(
                "Book",
                [
                    {
                        "type": "string_type",
                        "loc": ("pages", 0, "content", "illustration"),
                        "msg": "Input should be a valid string",
                        "input": illustration,
                    }
                ],
            )
        raise RuntimeError("another issue remains")

    monkeypatch.setattr(module, "_validate_book_data", validate)
    monkeypatch.setattr(
        module,
        "_write_repaired_book_json",
        lambda book_id, book_data: writes.append((book_id, book_data)),
    )

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(output_csv=output, repair=True)

    assert stats.non_compliant_books == 1
    assert stats.repair_attempted_books == 1
    assert stats.repaired_books == 0
    assert stats.repair_write_succeeded == 0
    assert writes == []

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert rows[0]["repair_attempted"] == "true"
    assert rows[0]["repair_applied"] == "true"
    assert rows[0]["repair_write_succeeded"] == "false"
    assert rows[0]["error_stage"] == "relationship_assignment"


def test_audit_repair_enabled_skips_dicts_without_url(monkeypatch, tmp_path):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={"book-a/book-a.json": True},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)

    payload = _invalid_illustration_book("book-a")
    payload["pages"][0]["content"]["illustration"] = {"expires_at": "soon"}

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: payload)

    def validate(book_data):
        raise ValidationError.from_exception_data(
            "Book",
            [
                {
                    "type": "string_type",
                    "loc": ("pages", 0, "content", "illustration"),
                    "msg": "Input should be a valid string",
                    "input": book_data["pages"][0]["content"]["illustration"],
                }
            ],
        )

    monkeypatch.setattr(module, "_validate_book_data", validate)

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(output_csv=output, repair=True)

    assert stats.non_compliant_books == 1
    assert stats.repaired_books == 0

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert rows[0]["repair_attempted"] == "true"
    assert rows[0]["repair_applied"] == "false"
    assert rows[0]["repair_count"] == "0"


def test_audit_repair_enabled_normalizes_signed_url_strings_on_compliant_books(
    monkeypatch, tmp_path
):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={"book-a/book-a.json": True},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)
    writes = []

    payload = _invalid_illustration_book("book-a")
    payload["pages"][0]["content"]["illustration"] = _signed_url("book-a", 1)

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: payload)
    monkeypatch.setattr(module, "_validate_book_data", lambda book_data: None)
    monkeypatch.setattr(
        module,
        "_write_repaired_book_json",
        lambda book_id, book_data: writes.append((book_id, book_data)),
    )

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(output_csv=output, repair=True)

    assert stats.compliant_books == 0
    assert stats.repair_attempted_books == 1
    assert stats.repaired_books == 1
    assert len(writes) == 1
    assert (
        writes[0][1]["pages"][0]["content"]["illustration"] == "book-a/images/1.png"
    )

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["repair_write_succeeded"] == "true"


def test_canonicalize_illustration_values_normalizes_dicts_and_strings():
    module = _load_script_module()
    payload = {
        "pages": [
            {
                "content": {
                    "illustration": {
                        "url": _signed_url("book-a", 1),
                        "expires_at": "soon",
                    }
                }
            },
            {
                "content": {
                    "illustration": _signed_url("book-a", 2)
                }
            },
            {
                "content": {
                    "illustration": "book-a/images/3.png"
                }
            },
        ]
    }

    normalized_count = module._canonicalize_illustration_values(payload)

    assert normalized_count == 2
    assert payload["pages"][0]["content"]["illustration"] == "book-a/images/1.png"
    assert payload["pages"][1]["content"]["illustration"] == "book-a/images/2.png"
    assert payload["pages"][2]["content"]["illustration"] == "book-a/images/3.png"


def test_audit_respects_book_id_limit_and_prefix(monkeypatch, tmp_path):
    module = _load_script_module()
    bucket = FakeBucket(
        [
            "alpha-1/alpha-1.json",
            "alpha-2/alpha-2.json",
            "beta-1/beta-1.json",
        ],
        existing={
            "alpha-1/alpha-1.json": True,
            "alpha-2/alpha-2.json": True,
            "beta-1/beta-1.json": True,
        },
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(module, "_load_book_json", lambda book_id: {"ok": True})
    monkeypatch.setattr(module, "_validate_book_data", lambda book_data: None)

    output = tmp_path / "report.csv"
    stats = module.audit_gcs_book_json_compliance(
        output_csv=output,
        prefix="alpha",
        limit=1,
    )

    assert stats.scanned_books == 1
    assert stats.compliant_books == 1

    output_specific = tmp_path / "report_specific.csv"
    stats_specific = module.audit_gcs_book_json_compliance(
        output_csv=output_specific,
        requested_book_ids=["beta-1"],
    )

    assert stats_specific.scanned_books == 1
    assert stats_specific.compliant_books == 1
