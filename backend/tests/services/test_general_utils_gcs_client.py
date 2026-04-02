from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import json

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

    saved_state = general_utils.save_book_library_state("book-local-1", True)
    assert saved_state["is_archived"] is True

    metadata_path = (
        tmp_path / "local_data" / "book-local-1" / general_utils.BOOK_METADATA_FILENAME
    )
    assert metadata_path.exists()

    persisted_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert persisted_payload["is_archived"] is True
    assert general_utils.get_book_library_state("book-local-1")["is_archived"] is True
