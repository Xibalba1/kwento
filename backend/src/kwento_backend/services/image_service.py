# backend/src/kwento_backend/services/image_service.py

import os
import logging

logger = logging.getLogger(__name__)


def save_image_locally(image_data: bytes, filename: str) -> str:
    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "wb") as f:
            f.write(image_data)
        logger.info(f"Saved image locally at {filename}")
        return filename
    except Exception as e:
        logger.error(f"Error saving image locally: {e}")
        raise


def save_image_to_cloud(image_data: bytes, filename: str) -> str:
    logger.info("save_image_to_cloud called, but cloud saving is not implemented yet.")
    print(f"image data: {image_data[:100]}...")
    print(f"filename: {filename}...")
    # TODO: Implement cloud saving logic
    return "cloud_url_stub"
