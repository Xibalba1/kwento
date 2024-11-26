# backend/src/utils/general_utils.py

from pathlib import Path
import logging
from google.cloud import storage
from google.oauth2 import service_account

try:
    from config import settings
except Exception as e:
    print(e)
import json

logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """
    Determines the project root by navigating up the directory tree until it finds
    a recognizable marker, such as a specific file or folder (e.g., pyproject.toml).
    """
    current_dir = Path(__file__).resolve()
    for parent in current_dir.parents:
        # Look for 'backend' as the specific project root marker
        if parent.name == "backend" and (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Project root could not be determined.")


def get_target_directory(relative_path: str) -> Path:
    """
    Gets or creates the target directory within the project based on a relative path
    from the project root.

    Args:
        relative_path (str): A relative path string to the target directory within the project.

    Returns:
        Path: The full path to the target directory.
    """
    # Get the project root dynamically
    project_root = get_project_root()

    # Determine the target directory path
    target_dir = project_root / relative_path

    # Create the directory if it doesn't exist
    target_dir.mkdir(parents=True, exist_ok=True)

    return target_dir


def get_gcs_file_cred_dir() -> str:
    """
    Gets the directory containing GCS credential file.
    """
    try:
        gcs_cred_dir = get_target_directory("secrets")
    except Exception as e:
        logger.error(f"Error locating GCS credentials directory: {e}")
    return gcs_cred_dir


def save_file(file_name: str, content: str, relative_path: str = "local_data") -> Path:
    """
    Saves a text file with given content to a target directory within the project.

    Args:
        file_name (str): The name of the file to save.
        content (str): The content to write into the file.
        relative_path (str): Relative path to the target directory within the project.

    Returns:
        Path: The path to the saved file.
    """
    # Get or create the target directory
    target_dir = get_target_directory(relative_path)

    # Define the full file path
    file_path = target_dir / file_name

    # Write content to the file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path


def save_binary_file(
    file_name: str, content: bytes, relative_path: str = "local_data"
) -> Path:
    """
    Saves a binary file with given content to a target directory within the project.

    Args:
        file_name (str): The name of the file to save.
        content (bytes): The binary content to write into the file.
        relative_path (str): Relative path to the target directory within the project.

    Returns:
        Path: The path to the saved file.
    """
    # Get or create the target directory
    target_dir = get_target_directory(relative_path)

    # Define the full file path
    file_path = target_dir / file_name

    # Write binary content to the file
    with open(file_path, "wb") as f:
        f.write(content)

    return file_path


def get_gcs_client() -> storage.Client:
    """
    Initializes and returns a Google Cloud Storage client using service account credentials.

    Returns:
        storage.Client: An instance of Google Cloud Storage client.
    """
    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.gcs_service_account_json
        )
        client = storage.Client(credentials=credentials, project=credentials.project_id)
        return client
    except Exception as e:
        logger.error(f"Error initializing GCS client: {e}")
        raise


def save_binary_file_to_gcs(
    file_name: str, content: bytes, relative_path: str = ""
) -> str:
    """
    Saves a binary file to Google Cloud Storage.

    Args:
        file_name (str): The name of the file to save.
        content (bytes): The binary content to write into the file.
        relative_path (str): The path within the bucket where the file will be saved.

    Returns:
        str: The GCS URL of the saved file.
    """
    try:
        bucket_name = settings.gcs_bucket_name
        if not bucket_name:
            raise ValueError("GCS bucket name is not configured.")

        client = get_gcs_client()
        bucket = client.bucket(bucket_name)

        # Construct the blob name
        if relative_path:
            blob_name = f"{relative_path}/{file_name}"
        else:
            blob_name = file_name

        blob = bucket.blob(blob_name)
        blob.upload_from_string(content)

        logger.info(f"Saved file to GCS at gs://{bucket_name}/{blob_name}")
        return f"gs://{bucket_name}/{blob_name}"
    except Exception as e:
        logger.error(f"Error saving file to GCS: {e}")
        raise


def save_file_to_gcs(file_name: str, content: str, relative_path: str = "") -> str:
    """
    Saves a text file to Google Cloud Storage.

    Args:
        file_name (str): The name of the file to save.
        content (str): The text content to write into the file.
        relative_path (str): The path within the bucket where the file will be saved.

    Returns:
        str: The GCS URL of the saved file.
    """
    try:
        bucket_name = settings.gcs_bucket_name
        if not bucket_name:
            raise ValueError("GCS bucket name is not configured.")

        client = get_gcs_client()
        bucket = client.bucket(bucket_name)

        # Construct the blob name
        if relative_path:
            blob_name = f"{relative_path}/{file_name}"
        else:
            blob_name = file_name

        blob = bucket.blob(blob_name)
        blob.upload_from_string(content, content_type="text/plain")

        logger.info(f"Saved file to GCS at gs://{bucket_name}/{blob_name}")
        return f"gs://{bucket_name}/{blob_name}"
    except Exception as e:
        logger.error(f"Error saving file to GCS: {e}")
        raise


def get_gcs_file_url(relative_filepath: str) -> str:
    """
    Generates a public URL for a file stored in GCS.

    Args:
        relative_filepath (str): The path within the bucket to the file.

    Returns:
        str: The public URL of the file.
    """
    bucket_name = settings.gcs_bucket_name
    return f"https://storage.googleapis.com/{bucket_name}/{relative_filepath}"


def write_json_file(
    file_name: str, data: dict, relative_path: str = "local_data"
) -> str:
    """
    Writes JSON data to a file, either locally or in GCS, based on settings.

    Args:
        file_name (str): The name of the file to save.
        data (dict): The JSON data to save.
        relative_path (str): The relative path or GCS folder to save in.

    Returns:
        str: The path or URL where the file was saved.
    """
    content = json.dumps(data, default=str)
    if settings.use_cloud_storage:
        return save_file_to_gcs(file_name, content, relative_path)
    else:
        local_path = save_file(file_name, content, relative_path)
        return str(local_path)


def read_json_file(file_name: str, relative_path: str = "local_data") -> dict:
    """
    Reads JSON data from a file, either locally or in GCS, based on settings.

    Args:
        file_name (str): The name of the file to read.
        relative_path (str): The relative path or GCS folder where the file is located.

    Returns:
        dict: The JSON data read from the file.
    """
    if settings.use_cloud_storage:
        bucket_name = settings.gcs_bucket_name
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob_name = f"{relative_path}/{file_name}" if relative_path else file_name
        blob = bucket.blob(blob_name)

        content = blob.download_as_text()
        return json.loads(content)
    else:
        file_path = get_target_directory(relative_path) / file_name
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)


def ensure_directory_exists(path: str):
    """
    Ensures a directory exists, supporting both local storage and GCS.

    Args:
        path (str): The directory or GCS path.
    """
    logger.debug(f"Called ensure_directory_exists with path: {path}")
    logger.debug(f"Settings.use_cloud_storage: {settings.use_cloud_storage}")

    if settings.use_cloud_storage:
        try:
            if "/" not in path:
                logger.error(f"Invalid GCS path: '{path}'. Must include a bucket name.")
                raise ValueError("Invalid GCS path. Format must be 'bucket_name/path'.")

            bucket_name, gcs_path = path.split("/", 1)
            logger.debug(f"Parsed bucket_name: '{bucket_name}', gcs_path: '{gcs_path}'")

            client = get_gcs_client()
            bucket = client.get_bucket(bucket_name)
            blob = bucket.blob(f"{gcs_path}/.keep")
            blob.upload_from_string("")  # Virtual directory creation
        except Exception as e:
            logger.error(f"Unable to confirm directory {path} exists: {e}")
            raise
    else:
        logger.debug(f"Ensuring local directory exists: {path}")
        Path(path).mkdir(parents=True, exist_ok=True)


def construct_storage_path(relative_path: str) -> str:
    """
    Constructs a storage path based on the configuration.

    If `use_cloud_storage` is True, prepends the GCS bucket name to the path.
    Otherwise, returns the local storage path.

    Args:
        relative_path (str): The relative path for the storage resource.

    Returns:
        str: The constructed storage path.
    """
    logger.debug(f"Constructing storage path for relative_path: {relative_path}")
    if settings.use_cloud_storage:
        if not settings.gcs_bucket_name:
            raise ValueError("GCS bucket name is not configured in settings.")
        return relative_path
    else:
        return str(Path("local_data") / relative_path)


if __name__ == "__main__":
    from pydantic import BaseSettings
    from pathlib import Path

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
        use_cloud_storage: bool = (
            True  # Default to False; set to True to use Google Cloud Storage
        )
        gcs_bucket_name: str = "kwento-books"  # GCS bucket name
        gcs_service_account_json: str = (
            get_gcs_cred_file_path()
        )  # Path GCP storage service account JSON key

        class Config:
            env_file = ".env"

    settings = Settings()

    ensure_directory_exists("antons_moon_adventure")
