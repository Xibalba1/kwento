# backend/src/kwento_backend/services/image_service.py
import logging

from kwento_backend.utils.general_utils import save_binary_file

logger = logging.getLogger(__name__)


def save_image_to_cloud(image_data: bytes, filename: str) -> str:
    """
    Save image data to the cloud. (Stub implementation)

    Args:
        image_data (bytes): The binary data of the image.
        filename (str): The name of the file to be saved in the cloud.

    Returns:
        str: A stub URL representing the cloud location.
    """
    logger.info("save_image_to_cloud called, but cloud saving is not implemented yet.")
    print(f"image data: {image_data[:100]}...")
    print(f"filename: {filename}...")
    # TODO: Implement cloud saving logic
    return "cloud_url_stub"


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
    image_data: bytes, relative_filepath: str, save_where: str = "local"
) -> str:
    """
    Save image data either locally or to the cloud based on the save_where parameter.

    Args:
        image_data (bytes): The binary data of the image.
        relative_filepath (str): The relative path (from project root) or filename where the image will be saved.
        save_where (str): Destination to save the image. Options: "local", "cloud".

    Returns:
        str: The path or URL where the image was saved.
    """
    if save_where == "local":
        return save_image_locally(image_data, relative_filepath)
    elif save_where == "cloud":
        return save_image_to_cloud(image_data, relative_filepath)
    else:
        logger.error(f"Invalid save_where parameter: {save_where}")
        raise ValueError("save_where must be either 'local' or 'cloud'")
