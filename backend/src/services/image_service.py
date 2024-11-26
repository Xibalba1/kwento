# backend/src/services/image_service.py

import logging
from typing import Optional

from utils.general_utils import (
    save_binary_file,
    save_binary_file_to_gcs,
    get_gcs_file_url,
    construct_storage_path,
)
from config import settings

logger = logging.getLogger(__name__)


def save_image_to_cloud(image_data: bytes, relative_filepath: str) -> str:
    """
    Save image data to Google Cloud Storage.

    Args:
        image_data (bytes): The binary data of the image.
        relative_filepath (str): The path within the bucket where the image will be saved.

    Returns:
        str: The public HTTP URL where the image was saved.
    """
    try:
        blob_name = save_binary_file_to_gcs(
            file_name=relative_filepath.split("/")[-1],
            content=image_data,
            relative_path="/".join(relative_filepath.split("/")[:-1]),
        )

        logger.info(f"Saved image to GCS at {blob_name}")

        # Use get_gcs_file_url to get the public HTTP URL
        public_url = get_gcs_file_url(blob_name)
        logger.info(f"Public URL for the image: {public_url}")

        return public_url
    except Exception as e:
        logger.error(f"Error saving image to cloud: {e}")
        raise


def save_image_locally(image_data: bytes, relative_filepath: str) -> str:
    """
    Save image data to a local file system using the save_binary_file utility.

    Args:
        image_data (bytes): The binary data of the image.
        relative_filepath (str): The relative path (from project root) where the image will be saved.

    Returns:
        str: The filepath where the image was saved.
    """
    try:
        # Save the binary image data using the utility function
        saved_path = save_binary_file(
            file_name=relative_filepath.split("/")[-1],
            content=image_data,
            relative_path="/".join(relative_filepath.split("/")[:-1]) or "local_data",
        )
        logger.info(f"Saved image locally at {saved_path}")
        return str(saved_path)
    except Exception as e:
        logger.error(f"Error saving image locally: {e}")
        raise


def save_image(
    image_data: bytes, relative_filepath: str, save_where: Optional[str] = None
) -> str:
    """
    Save image data either locally or to the cloud based on the save_where parameter.

    Args:
        image_data (bytes): The binary data of the image.
        relative_filepath (str): The relative path (from project root) or filename where the image will be saved.
        save_where (str, optional): Destination to save the image. Options: "local", "cloud".

    Returns:
        str: The path or URL where the image was saved.
    """
    if save_where is None:
        save_where = "cloud" if settings.use_cloud_storage else "local"

    if save_where == "local":
        return save_image_locally(image_data, relative_filepath)
    elif save_where == "cloud":
        return save_image_to_cloud(image_data, relative_filepath)
    else:
        logger.error(f"Invalid save_where parameter: {save_where}")
        raise ValueError("save_where must be either 'local' or 'cloud'")
