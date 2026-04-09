from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import json
from datetime import datetime, timezone
import os

from src.utils import general_utils


@patch("src.utils.general_utils.storage.Client")
@patch("src.utils.general_utils.service_account.Credentials.from_service_account_info")
def test_get_gcs_client_is_cached(mock_from_service_account_info, mock_storage_client):
    general_utils._reset_gcs_client_cache()
    mock_from_service_account_info.return_value = SimpleNamespace(project_id="project-1")
    mock_storage_client.return_value = SimpleNamespace(name="client")

    client_one = general_utils.get_gcs_client()
    client_two = general_utils.get_gcs_client()

    assert client_one is client_two
    assert mock_from_service_account_info.call_count == 1
    assert mock_storage_client.call_count == 1
    general_utils._reset_gcs_client_cache()


def test_book_library_state_defaults_and_round_trips_locally(tmp_path, monkeypatch):
    monkeypatch.setattr(general_utils.settings, "use_cloud_storage", False)
    monkeypatch.setattr(general_utils.settings, "local_data_path", str(tmp_path / "local_data"))

    default_state = general_utils.get_book_library_state("book-local-1")
    assert default_state["is_archived"] is False
    assert default_state["is_favorite"] is False

    saved_state = general_utils.save_book_library_state("book-local-1", is_archived=True)
    assert saved_state["is_archived"] is True
    assert saved_state["is_favorite"] is False

    metadata_path = (
        tmp_path / "local_data" / "book-local-1" / general_utils.BOOK_METADATA_FILENAME
    )
    assert metadata_path.exists()

    persisted_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert persisted_payload["is_archived"] is True
    assert persisted_payload["is_favorite"] is False
    assert general_utils.get_book_library_state("book-local-1")["is_archived"] is True


def test_book_library_state_normalizes_archive_and_favorite_invariants(tmp_path, monkeypatch):
    monkeypatch.setattr(general_utils.settings, "use_cloud_storage", False)
    monkeypatch.setattr(general_utils.settings, "local_data_path", str(tmp_path / "local_data"))

    favorited_state = general_utils.save_book_library_state(
        "book-local-2",
        is_favorite=True,
    )
    assert favorited_state["is_favorite"] is True
    assert favorited_state["is_archived"] is False

    archived_state = general_utils.save_book_library_state(
        "book-local-2",
        is_archived=True,
    )
    assert archived_state["is_archived"] is True
    assert archived_state["is_favorite"] is False

    restored_favorite_state = general_utils.save_book_library_state(
        "book-local-2",
        is_favorite=True,
    )
    assert restored_favorite_state["is_favorite"] is True
    assert restored_favorite_state["is_archived"] is False

    unfavorited_state = general_utils.save_book_library_state(
        "book-local-2",
        is_favorite=False,
    )
    assert unfavorited_state["is_favorite"] is False
    assert unfavorited_state["is_archived"] is False

    rearchived_state = general_utils.save_book_library_state(
        "book-local-2",
        is_archived=True,
    )
    assert rearchived_state["is_archived"] is True
    assert rearchived_state["is_favorite"] is False

    restored_from_archive_state = general_utils.save_book_library_state(
        "book-local-2",
        is_favorite=True,
    )
    assert restored_from_archive_state["is_favorite"] is True
    assert restored_from_archive_state["is_archived"] is False


def test_book_library_state_normalizes_legacy_inconsistent_metadata_on_read(tmp_path, monkeypatch):
    monkeypatch.setattr(general_utils.settings, "use_cloud_storage", False)
    monkeypatch.setattr(general_utils.settings, "local_data_path", str(tmp_path / "local_data"))

    metadata_path = (
        tmp_path / "local_data" / "book-local-3" / general_utils.BOOK_METADATA_FILENAME
    )
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "book_id": "book-local-3",
                "is_archived": True,
                "is_favorite": True,
                "updated_at": "2026-04-07T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    normalized_state = general_utils.get_book_library_state("book-local-3")

    assert normalized_state["is_archived"] is True
    assert normalized_state["is_favorite"] is False


def test_get_book_by_id_returns_local_created_at(tmp_path, monkeypatch):
    monkeypatch.setattr(general_utils.settings, "use_cloud_storage", False)
    monkeypatch.setattr(general_utils.settings, "local_data_path", str(tmp_path / "local_data"))

    book_dir = tmp_path / "local_data" / "book-local-created"
    book_dir.mkdir(parents=True, exist_ok=True)
    book_json_path = book_dir / "book-local-created.json"
    book_json_path.write_text(
        json.dumps(
            {
                "book_id": "book-local-created",
                "book_title": "Created Locally",
                "pages": [],
            }
        ),
        encoding="utf-8",
    )

    created_at = datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc).timestamp()
    os.utime(book_json_path, (created_at, created_at))

    book = general_utils.get_book_by_id("book-local-created")

    assert book["created_at"] == "2026-04-09T12:00:00+00:00"
