from unittest.mock import patch

from src.services import image_service


@patch("src.services.image_service.save_binary_file_to_gcs")
def test_save_image_to_cloud_returns_blob_path(mock_save_binary_file_to_gcs):
    mock_save_binary_file_to_gcs.return_value = "book-id/images/1.png"

    path = image_service.save_image_to_cloud(b"img", "book-id/images/1.png")

    assert path == "book-id/images/1.png"
    mock_save_binary_file_to_gcs.assert_called_once()
