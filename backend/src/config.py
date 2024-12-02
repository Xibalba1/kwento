# backend/src/config.py

from pydantic import BaseSettings
from pathlib import Path
import logging


def get_gcs_cred_file_path() -> str:
    """
    Gets the path of the GCS credentials file for the project.

    Due to project structure and entrypoint, we need to get the
    absolute path of this file.
    """
    try:
        # Get the project root dynamically
        current_dir = Path(__file__).resolve()
        for parent in current_dir.parents:
            # Look for 'backend' as the specific project root marker
            if parent.name == "kwento" and (parent / ".gitignore").exists():
                project_root = parent
                break

        # Determine the target directory path
        gcs_cred_dir = project_root / "secrets"

        # Create the directory if it doesn't exist
        gcs_cred_dir.mkdir(parents=True, exist_ok=True)

        gcs_cred_fp = gcs_cred_dir / "kwento-88cf359a16d5.json"
    except Exception as e:
        raise RuntimeError("GCS credentials cannot be located.")
    return str(gcs_cred_fp)


class Settings(BaseSettings):
    openai_api_key: str
    local_data_path: str = "local_data"
    use_cloud_storage: bool = (
        False  # Default to False; set to True to use Google Cloud Storage
    )
    gcs_bucket_name: str = "kwento-books"  # GCS bucket name
    gcs_service_account_json: str = (
        get_gcs_cred_file_path()
    )  # Path GCP storage service account JSON key
    logging_level = logging.DEBUG

    class Config:
        env_file = ".env"


settings = Settings()
settings.use_cloud_storage = True
