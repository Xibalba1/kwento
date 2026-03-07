from types import SimpleNamespace
from unittest.mock import patch

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
