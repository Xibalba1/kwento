# backend/src/services/image_service.py

import logging

from utils.general_utils import (
    save_binary_file,
    save_binary_file_to_gcs,
    get_logger,
)
from config import settings


logger = get_logger(__name__)


def save_image_to_cloud(image_data: bytes, relative_filepath: str) -> str:
    """
    Save image data to Google Cloud Storage and return the blob path.

    Args:
        image_data (bytes): The binary data of the image.
        relative_filepath (str): The path within the bucket where the image will be saved.

    Returns:
        str: The blob path of the uploaded image.
    """
    try:
        blob_name = save_binary_file_to_gcs(
            file_name=relative_filepath.split("/")[-1],
            content=image_data,
            relative_path="/".join(relative_filepath.split("/")[:-1]),
            content_type="image/png",
        )

        logger.info(f"Saved image to GCS at {blob_name}")

        return blob_name
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


def save_image(image_data: bytes, relative_filepath: str) -> str:
    """
    Save image data either locally or to the cloud based on the save_where parameter.

    Args:
        image_data (bytes): The binary data of the image.
        relative_filepath (str): The relative path (from project root) or filename where the image will be saved.

    Returns:
        str: The path or URL where the image was saved.
    """
    try:
        if settings.use_cloud_storage == False:
            return save_image_locally(image_data, relative_filepath)
        elif settings.use_cloud_storage == True:
            return save_image_to_cloud(image_data, relative_filepath)
        else:
            logger.error(f"Unable to determine save destination (local or cloud)")
            raise ValueError("`settings.use_cloud_storage` must have a value.")
    except Exception as e:
        logger.error(f"Failed to save image with exception {e}")
        raise
