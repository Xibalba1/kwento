# Path: /backend/scripts/assign_uuid_to_existing_books.py

import os
import json
import uuid
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def assign_uuid_to_books(local_data_path: Path):
    if not local_data_path.exists():
        logger.error(f"local_data directory not found at {local_data_path}")
        return

    book_dirs = [d for d in local_data_path.iterdir() if d.is_dir()]

    for book_dir in book_dirs:
        json_files = [f for f in book_dir.iterdir() if f.suffix == ".json"]
        if not json_files:
            logger.warning(f"No JSON file found in {book_dir}. Skipping.")
            continue

        book_json_path = json_files[0]
        with open(book_json_path, "r", encoding="utf-8") as f:
            book_data = json.load(f)

        if "book_id" not in book_data:
            new_uuid = str(uuid.uuid4())
            book_data["book_id"] = new_uuid
            with open(book_json_path, "w", encoding="utf-8") as f:
                json.dump(book_data, f, indent=4)
            logger.info(
                f"Assigned UUID {new_uuid} to book '{book_data.get('book_title', 'Untitled')}'"
            )
        else:
            logger.info(
                f"Book '{book_data.get('book_title', 'Untitled')}' already has a UUID."
            )


if __name__ == "__main__":
    # Define the path to local_data
    current_file = Path(__file__).resolve()
    local_data_path = (
        current_file.parents[2] / "local_data"
    )  # Adjust based on directory depth

    assign_uuid_to_books(local_data_path)
