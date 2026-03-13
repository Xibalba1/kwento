import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "backfill_missing_gcs_covers.py"
    )
    spec = importlib.util.spec_from_file_location("backfill_missing_gcs_covers", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeBlob:
    def __init__(self, name, *, exists=True, payload=b""):
        self.name = name
        self._exists = exists
        self._payload = payload

    def exists(self):
        return self._exists

    def download_as_bytes(self):
        return self._payload


class FakeBucket:
    def __init__(self, names, *, existing=None, payloads=None):
        self._list_blobs = [FakeBlob(name) for name in names]
        self._existing = existing or {}
        self._payloads = payloads or {}

    def list_blobs(self, prefix=None):
        if prefix is None:
            return list(self._list_blobs)
        return [blob for blob in self._list_blobs if blob.name.startswith(prefix)]

    def blob(self, name):
        return FakeBlob(
            name,
            exists=self._existing.get(name, False),
            payload=self._payloads.get(name, b""),
        )


def test_discover_candidate_book_ids_skips_invalid_prefixes_and_limits():
    module = _load_script_module()
    stats = module.BackfillStats()
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


def test_backfill_missing_covers_dry_run_reports_existing_and_missing_seed(monkeypatch):
    module = _load_script_module()
    bucket = FakeBucket(
        [
            "book-a/book-a.json",
            "book-b/book-b.json",
            "book-c/book-c.json",
        ],
        existing={
            "book-a/book-a.json": True,
            "book-a/cover.png": True,
            "book-b/book-b.json": True,
            "book-b/cover.png": False,
            "book-b/images/1.png": True,
            "book-c/book-c.json": True,
            "book-c/cover.png": False,
            "book-c/images/1.png": False,
        },
        payloads={"book-b/images/1.png": b"seed"},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")

    called = {"value": False}

    async def fake_generate_cover(book, reference_image_bytes):
        called["value"] = True
        return {"saved_path": f"{book.book_id}/cover.png"}

    monkeypatch.setattr(module, "_generate_cover", fake_generate_cover)

    stats = module.backfill_missing_covers(execute=False)

    assert stats.scanned_books == 3
    assert stats.already_had_cover == 1
    assert stats.generated_cover == 0
    assert stats.skipped_missing_seed_page_image == 1
    assert stats.failed_generation == 0
    assert called["value"] is False


def test_backfill_missing_covers_execute_generates_cover(monkeypatch):
    module = _load_script_module()
    bucket = FakeBucket(
        ["book-a/book-a.json"],
        existing={
            "book-a/book-a.json": True,
            "book-a/cover.png": False,
            "book-a/images/1.png": True,
        },
        payloads={"book-a/images/1.png": b"seed"},
    )
    client = SimpleNamespace(bucket=lambda bucket_name: bucket)

    monkeypatch.setattr(module, "get_gcs_client", lambda: client)
    monkeypatch.setattr(module.settings, "use_cloud_storage", True)
    monkeypatch.setattr(module.settings, "gcs_bucket_name", "kwento-books")
    monkeypatch.setattr(
        module,
        "_load_book",
        lambda book_id: SimpleNamespace(book_id=book_id),
    )

    generated = {"calls": 0}

    async def fake_generate_cover(book, reference_image_bytes):
        generated["calls"] += 1
        assert reference_image_bytes == b"seed"
        return {"saved_path": f"{book.book_id}/cover.png"}

    monkeypatch.setattr(module, "_generate_cover", fake_generate_cover)

    stats = module.backfill_missing_covers(execute=True)

    assert generated["calls"] == 1
    assert stats.scanned_books == 1
    assert stats.generated_cover == 1
    assert stats.failed_generation == 0
