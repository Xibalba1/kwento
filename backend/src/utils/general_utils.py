# backend/src/utils/general_utils.py

from pathlib import Path
import logging
import threading
from google.cloud import storage
from google.oauth2 import service_account
from typing import List, Dict, Any
import json
from datetime import datetime, timedelta, timezone

try:
    from config import settings
except Exception as e:
    print(
        f"Unable to import settings. Application cannot function without this data: {e}"
    )


class CustomRailwayLogFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.name,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def get_logger(module_name):
    """
    Modifies logger for Railway deployment.
    """
    logger = logging.getLogger(module_name)
    logger.setLevel(settings.logging_level)
    handler = logging.StreamHandler()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    formatter = CustomRailwayLogFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = get_logger(__name__)
_GCS_CLIENT = None
_GCS_CLIENT_LOCK = threading.Lock()


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
    global _GCS_CLIENT
    try:
        if _GCS_CLIENT is not None:
            return _GCS_CLIENT

        with _GCS_CLIENT_LOCK:
            if _GCS_CLIENT is not None:
                return _GCS_CLIENT

            credentials = service_account.Credentials.from_service_account_info(
                settings.gcs_service_account_json
            )
            _GCS_CLIENT = storage.Client(
                credentials=credentials, project=credentials.project_id
            )
            return _GCS_CLIENT
    except Exception as e:
        logger.error(f"Error initializing GCS client: {e}")
        raise


def _reset_gcs_client_cache() -> None:
    """
    Test helper to reset cached GCS client instance.
    """
    global _GCS_CLIENT
    with _GCS_CLIENT_LOCK:
        _GCS_CLIENT = None


def save_binary_file_to_gcs(
    file_name: str,
    content: bytes,
    relative_path: str = "",
    content_type: str = "image/png",
) -> str:
    """
    Saves a binary file to Google Cloud Storage.

    Args:
        file_name (str): The name of the file to save.
        content (bytes): The binary content to write into the file.
        relative_path (str): The path within the bucket where the file will be saved.
        content_type (str): MIME type as per IANA definitions

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
        blob.upload_from_string(content, content_type=content_type)

        logger.info(f"Saved file to GCS at gs://{bucket_name}/{blob_name}")
        return blob_name
    except Exception as e:
        logger.error(f"Error saving file to GCS: {e}")
        raise


def save_file_to_gcs(
    file_name: str,
    content: str,
    relative_path: str = "",
    content_type="application/json",
    metadata: dict = None,
) -> str:
    """
    Saves a text file to Google Cloud Storage with optional metadata.

    Args:
        file_name (str): The name of the file to save.
        content (str): The text content to write into the file.
        relative_path (str): The path within the bucket where the file will be saved.
        content_type (str): MIME type of the content.
        metadata (dict): Optional metadata to set on the blob.

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
        blob.metadata = metadata
        blob.upload_from_string(content, content_type=content_type)

        logger.info(f"Saved file to GCS at gs://{bucket_name}/{blob_name}")
        return blob_name
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
    file_name: str, data: dict, relative_path: str = "local_data", metadata: dict = None
) -> str:
    """
    Writes JSON data to a file, either locally or in GCS, based on settings.

    Args:
        file_name (str): The name of the file to save.
        data (dict): The JSON data to save.
        relative_path (str): The relative path or GCS folder to save in.
        metadata (dict): Optional metadata to set on the file (GCS only).

    Returns:
        str: The path or URL where the file was saved.
    """
    content = json.dumps(data, default=str)
    if settings.use_cloud_storage:
        return save_file_to_gcs(
            file_name,
            content,
            relative_path,
            content_type="application/json",
            metadata=metadata,
        )
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


def get_book_list() -> List[Dict[str, Any]]:
    """
    Returns a list of books, each represented as a dictionary with metadata, pre-signed URLs, and images.
    """
    books_dict = {}
    books_list: List[Dict[str, Any]] = []

    if settings.use_cloud_storage:
        # Use GCS
        try:
            client = get_gcs_client()
            bucket = client.bucket(settings.gcs_bucket_name)

            # List all blobs
            blobs = bucket.list_blobs()

            expiration_time = timedelta(hours=1)
            expires_at = datetime.now(timezone.utc) + expiration_time

            for blob in blobs:
                blob_name = blob.name

                # Process JSON files
                if blob_name.endswith(".json"):
                    parts = blob_name.split("/")
                    if len(parts) != 2 or parts[1] != f"{parts[0]}.json":
                        continue

                    # Ensure metadata is loaded
                    blob.reload()
                    metadata = blob.metadata or {}
                    if metadata.get("artifact_type") not in {None, "book_json"}:
                        continue
                    book_id = metadata.get("book_id")
                    book_title = metadata.get("book_title")
                    logger.debug(
                        f"get_book_list(): `book_id` {book_id} | `book_title` {book_title}"
                    )

                    if book_id and book_title:
                        # Generate pre-signed URL for the JSON metadata
                        json_url = generate_presigned_url(blob_name, expiration=3600)

                        # Initialize book entry if not already present
                        if book_id not in books_dict:
                            books_dict[book_id] = {
                                "book_id": book_id,
                                "book_title": book_title,
                                "json_url": json_url,
                                "expires_at": expires_at,
                                "images": [],
                            }
                        else:
                            # Update json_url and book_title if needed
                            books_dict[book_id]["json_url"] = json_url
                            books_dict[book_id]["book_title"] = book_title
                    else:
                        logger.error(f"Missing metadata for blob {blob_name}")

                # Process image files
                elif blob_name.endswith(".png"):
                    # Assuming images are stored under {book_id}/images/{page}.png
                    parts = blob_name.split("/")
                    if len(parts) >= 3 and parts[1] == "images":
                        book_id = parts[0]
                        page_str = parts[2].replace(".png", "")
                        try:
                            page = int(page_str)
                        except ValueError:
                            logger.error(
                                f"Invalid page number in blob name {blob_name}"
                            )
                            continue

                        # Generate pre-signed URL for the image
                        image_url = generate_presigned_url(blob_name, expiration=3600)

                        # Initialize book entry if not already present
                        if book_id not in books_dict:
                            books_dict[book_id] = {
                                "book_id": book_id,
                                "book_title": "",  # Will be updated when JSON is processed
                                "json_url": "",  # Will be updated when JSON is processed
                                "expires_at": expires_at,
                                "images": [],
                            }

                        # Add image to the book's images
                        books_dict[book_id]["images"].append(
                            {
                                "page": page,
                                "url": image_url,
                                "expires_at": expires_at,
                            }
                        )
                else:
                    # Skip other files
                    continue

            # Convert books_dict to a list
            books_list = list(books_dict.values())

            # Optional: Sort images by page number for each book
            for book in books_list:
                book["images"].sort(key=lambda x: x["page"])

            return books_list

        except Exception as e:
            logger.error(f"Error accessing cloud storage: {e}")
            return []
    else:
        try:
            local_data_path = Path(settings.local_data_path)
            logger.debug(f"'local_data_path': {local_data_path}")
            expiration_time = timedelta(hours=1)
            expires_at = datetime.now(timezone.utc) + expiration_time

            if not local_data_path.exists():
                logger.error(f"local_data directory not found at {local_data_path}")
                return books_list

            # Get list of subdirectories (each corresponds to a book)
            book_dirs = [d for d in local_data_path.iterdir() if d.is_dir()]

            if not book_dirs:
                logger.error("No books found in local_data directory.")
                return books_list

            for book_dir in book_dirs:
                # Find the JSON file in the book directory
                book_json_path = book_dir / f"{book_dir.name}.json"
                if not book_json_path.exists():
                    continue  # Skip if no JSON file found

                # Read the JSON file using the utility function
                try:
                    book_data = read_json_file(
                        book_json_path.name, relative_path=book_dir.name
                    )
                except Exception as e:
                    logger.error(f"Error loading JSON for {book_json_path}: {e}")
                    continue  # Skip this book

                # Validate required fields
                if "book_title" not in book_data or "book_id" not in book_data:
                    continue  # Skip if title or book_id is missing

                books_list.append(
                    {
                        "book_id": str(book_data["book_id"]),
                        "book_title": book_data["book_title"],
                        "json_url": str(book_json_path.resolve()),
                        "expires_at": datetime.now(timezone.utc) + expiration_time,
                        "images": [
                            {
                                "page": page_data["page_number"],
                                "url": str(
                                    (book_dir / f"images/{page_data['page_number']}.png").resolve()
                                ),
                                "expires_at": expires_at,
                            }
                            for page_data in book_data.get("pages", [])
                            if isinstance(page_data, dict)
                            and isinstance(page_data.get("page_number"), int)
                        ],
                    }
                )
        except Exception as e:
            logger.exception(f"Unexpected error listing books: {e}")
            return books_list

    return books_list


def get_book_by_id(book_id: str) -> Dict[str, Any]:
    """
    Fetches metadata and pre-signed URLs for a specific book by its ID.

    Args:
        book_id (str): The unique identifier for the book.

    Returns:
        Dict[str, Any]: Metadata and pre-signed URLs for the book.
    """
    try:
        logger.debug(f"get_book_by_id(): getting book by id: {book_id}")
        if settings.use_cloud_storage:
            # Use GCS logic
            client = get_gcs_client()
            bucket = client.bucket(settings.gcs_bucket_name)
            logger.debug(f"get_book_by_id():got client and bucket")

            # Locate the JSON metadata for the book
            book_blob_name = f"{book_id}/{book_id}.json"
            book_blob = bucket.blob(book_blob_name)
            logger.debug(
                f"get_book_by_id(): set `book_blob_name` {book_blob_name} and `book_blob`"
            )

            if not book_blob.exists():
                raise ValueError(f"Book with ID {book_id} not found in GCS.")

            logger.debug(f"get_book_by_id(): `book_id` '{book_id}' exists in GCS.")
            # Generate pre-signed URL for the JSON metadata
            json_url = generate_presigned_url(book_blob_name, expiration=3600)
            logger.debug(
                f"get_book_by_id(): presigned url generated for `book_id`: {json_url}"
            )

            # Load metadata from the blob
            book_blob.reload()
            metadata = book_blob.metadata or {}
            book_title = metadata.get("book_title", "Unknown Title")
            logger.debug(
                f"get_book_by_id(): `book_blob` reloaded. `metadata` set. `book_title` set."
            )

            # Locate and generate pre-signed URLs for images
            image_blobs = list(bucket.list_blobs(prefix=f"{book_id}/images/"))
            expiration_time = timedelta(hours=1)
            expires_at = datetime.now(timezone.utc) + expiration_time

            images = [
                {
                    "page": int(image_blob.name.split("/")[-1].replace(".png", "")),
                    "url": generate_presigned_url(image_blob.name, expiration=3600),
                    "expires_at": expires_at,
                }
                for image_blob in image_blobs
            ]

            # Construct and return the book's metadata and URLs
            return {
                "book_id": book_id,
                "book_title": book_title,
                "json_url": json_url,
                "expires_at": expires_at,
                "images": images,
            }
        else:
            # Use local storage logic
            local_data_path = Path(settings.local_data_path)
            if not local_data_path.exists():
                raise ValueError(f"Local data directory not found at {local_data_path}")

            # Locate the book directory
            book_dir = local_data_path / book_id
            if not book_dir.exists():
                raise ValueError(f"Book with ID {book_id} not found in local storage.")

            # Locate the JSON metadata file
            book_json_path = book_dir / f"{book_id}.json"
            if not book_json_path.exists():
                raise ValueError(f"No metadata file found for book ID {book_id}.")

            try:
                book_data = read_json_file(book_json_path.name, relative_path=book_id)
            except Exception as e:
                raise ValueError(f"Error reading JSON for {book_json_path}: {e}")

            # Extract metadata and construct response
            book_title = book_data.get("book_title", "Unknown Title")
            expiration_time = timedelta(hours=1)
            expires_at = datetime.now(timezone.utc) + expiration_time

            images = [
                {
                    "page": page_data["page_number"],
                    "url": str(
                        (book_dir / f"images/{page_data['page_number']}.png").resolve()
                    ),  # Local path
                    "expires_at": expires_at,
                }
                for page_data in book_data.get("pages", [])
                if isinstance(page_data, dict)
                and isinstance(page_data.get("page_number"), int)
            ]

            return {
                "book_id": book_id,
                "book_title": book_title,
                "json_url": str(book_json_path.resolve()),  # Local path
                "expires_at": expires_at,
                "images": images,
            }

    except ValueError as e:
        logger.error(f"ValueError in get_book_by_id: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error fetching book with ID {book_id}: {e}")
        raise


def generate_presigned_url(blob_name: str, expiration: int = 3600) -> str:
    """
    Generates a pre-signed URL for a blob in Google Cloud Storage.

    Args:
        blob_name (str): Path to the blob in the GCS bucket.
        expiration (int): URL expiration time in seconds (default: 3600 seconds [1 hour]).

    Returns:
        str: A pre-signed URL for the blob.
    """
    try:
        bucket_name = settings.gcs_bucket_name
        if not bucket_name:
            raise ValueError("GCS bucket name is not configured.")

        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Generate the signed URL
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration),
            method="GET",
        )
        return url
    except Exception as e:
        logger.error(f"Error generating pre-signed URL: {e}")
        raise
