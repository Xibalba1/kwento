# backend/src/api/routers/books.py

import random
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from api.models.book_models import Book
from core import content_generation
from utils.general_utils import read_json_file

router = APIRouter()
logger = logging.getLogger(__name__)


class BookCreateRequest(BaseModel):
    theme: str


class PageResponse(BaseModel):
    page_number: int
    text_content: str
    illustration_b64_data: str
    illustration: Optional[str] = None  # Add this field
    characters: List[str]


class BookResponse(BaseModel):
    book_id: str
    title: str
    pages: List[PageResponse]


@router.post("/", response_model=BookResponse)
async def create_book(book_request: BookCreateRequest):
    """
    Endpoint to create a new book based on a given theme.
    """
    logger.info(f"Received request to create book with theme: '{book_request.theme}'")
    try:
        book = await content_generation.generate_book(book_request.theme)
        logger.info(
            f"Generated book titled: '{book.book_title}' with {len(book.pages)} pages."
        )

        response = BookResponse(
            book_id=str(book.book_id),
            title=book.book_title,
            pages=[
                PageResponse(
                    page_number=page.page_number,
                    text_content=page.content.text_content_of_this_page,
                    illustration=page.content.illustration,  # Include the illustration URL or path
                    characters=page.content.characters_in_this_page,
                )
                for page in book.pages
            ],
        )
        logger.info(
            f"Successfully constructed BookResponse for book '{book.book_title}'."
        )
        return response
    except Exception as e:
        logger.exception(f"Error creating book: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating book: {e}")


@router.get("/random/", response_model=BookResponse)
async def get_random_book():
    """
    Fetches a random book from the local_data directory and returns its JSON content.
    """
    logger.info("Received request to fetch a random book.")
    try:
        # Determine the absolute path to the local_data directory
        current_file = Path(__file__).resolve()
        # Adjust the number based on directory depth; assuming this file is at backend/src/api/routers/
        local_data_path = (
            current_file.parents[3] / "local_data"
        )  # backend/src/api/routers/../../local_data

        logger.debug(f"Resolved local_data_path to: {local_data_path}")

        if not local_data_path.exists():
            logger.error(f"local_data directory not found at {local_data_path}")
            raise HTTPException(
                status_code=500, detail="local_data directory not found."
            )

        # Get list of subdirectories (each corresponds to a book)
        book_dirs = [d for d in local_data_path.iterdir() if d.is_dir()]
        logger.debug(f"Found {len(book_dirs)} book directories in local_data.")

        if not book_dirs:
            logger.error("No books found in local_data directory.")
            raise HTTPException(status_code=404, detail="No books available.")

        # Select a random book directory
        selected_book_dir = random.choice(book_dirs)
        logger.debug(f"Selected book directory: {selected_book_dir}")

        # Find the JSON file in the selected directory
        json_files = [f for f in selected_book_dir.iterdir() if f.suffix == ".json"]
        logger.debug(f"Found {len(json_files)} JSON files in selected book directory.")

        if not json_files:
            logger.error(
                f"No JSON file found in the selected book directory: {selected_book_dir}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"No JSON file found in directory: {selected_book_dir}",
            )

        book_json_path = json_files[0]
        logger.debug(f"Book JSON path: {book_json_path}")

        # Read the JSON file
        try:
            book_data = read_json_file(book_json_path, "books")
            logger.debug(f"Successfully loaded JSON data from {book_json_path}")
        except Exception as e:
            logger.error(f"JSON decode error for file {book_json_path}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON format in book file: {book_json_path}",
            )
        # TODO: deprecated, remove following block
        # with open(book_json_path, "r", encoding="utf-8") as f:
        #     try:
        #         book_data = json.load(f)
        #         logger.debug(f"Successfully loaded JSON data from {book_json_path}")
        #     except json.JSONDecodeError as jde:
        #         logger.error(f"JSON decode error for file {book_json_path}: {jde}")
        #         raise HTTPException(
        #             status_code=500,
        #             detail=f"Invalid JSON format in book file: {book_json_path}",
        #         )

        # Validate required fields
        required_fields = ["book_title", "pages"]
        for field in required_fields:
            if field not in book_data:
                logger.error(f"Missing required field '{field}' in {book_json_path}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Missing required field '{field}' in book data.",
                )

        # Assign a UUID if not present
        # if "book_id" not in book_data:
        #     book_data["book_id"] = str(uuid4())  # Assign a new UUID as a string
        #     # Save the updated JSON back to the file
        #     with open(book_json_path, "w", encoding="utf-8") as f:
        #         json.dump(book_data, f, indent=4)
        #     logger.info(
        #         f"Assigned new UUID to book '{book_data['book_title']}' and updated JSON file."
        #     )

        # Parse the JSON data into the Book model for validation
        try:
            book = Book(**book_data)
            logger.debug(
                f"Successfully parsed JSON data into Book model for '{book.book_title}'."
            )
            logger.debug(f"book.book_id: {book.book_id} (type: {type(book.book_id)})")
        except Exception as e:
            logger.error(f"Error parsing JSON data into Book model: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error parsing book data: {e}",
            )

        # Transform the data to match BookResponse
        try:
            response = {
                "book_id": str(book.book_id),  # Ensuring book_id is a string
                "title": book.book_title,
                "pages": [
                    {
                        "page_number": page.page_number,
                        "text_content": page.content.text_content_of_this_page,
                        "illustration_b64_data": page.content.illustration_b64_data,
                        "characters": page.content.characters_in_this_page,
                    }
                    for page in book.pages
                ],
            }
            logger.debug(f"Constructed response dictionary: {response}")
        except KeyError as ke:
            logger.error(f"Missing key during response construction: {ke}")
            raise HTTPException(
                status_code=500,
                detail=f"Missing key during response construction: {ke}",
            )
        except Exception as e:
            logger.error(f"Error during response construction: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error constructing response: {e}",
            )

        # Validate the response against BookResponse model
        try:
            book_response = BookResponse(**response)
            logger.info(
                f"Successfully constructed BookResponse for book '{book.book_title}'."
            )
        except Exception as e:
            logger.error(f"Response validation error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Response validation error: {e}",
            )

        return book_response

    except HTTPException as he:
        # Re-raise HTTPExceptions to be handled by FastAPI
        logger.exception(f"HTTPException occurred: {he.detail}")
        raise he
    except Exception as e:
        # Log unexpected exceptions and return a generic error message
        logger.exception(f"Unexpected error fetching random book: {e}")
        raise HTTPException(status_code=500, detail="Error fetching random book.")


@router.get("/", response_model=List[Dict[str, Any]])
async def list_books():
    """
    Lists all existing books.
    """
    logger.info("Received request to list all books.")
    try:
        # Determine the absolute path to the local_data directory
        current_file = Path(__file__).resolve()
        local_data_path = current_file.parents[3] / "local_data"

        if not local_data_path.exists():
            logger.error(f"local_data directory not found at {local_data_path}")
            raise HTTPException(
                status_code=500, detail="local_data directory not found."
            )

        # Get list of subdirectories (each corresponds to a book)
        book_dirs = [d for d in local_data_path.iterdir() if d.is_dir()]

        if not book_dirs:
            logger.error("No books found in local_data directory.")
            raise HTTPException(status_code=404, detail="No books available.")

        books_list = []

        for book_dir in book_dirs:
            # Find the JSON file in the book directory
            json_files = [f for f in book_dir.iterdir() if f.suffix == ".json"]
            if not json_files:
                continue  # Skip if no JSON file found
            book_json_path = json_files[0]

            # Read the JSON file
            try:
                book_data = read_json_file(book_json_path, "books")
            except Exception as e:
                logger.error(f"Error loading JSON for {book_json_path}: {e}")

            # TODO: deprecated, remove after testing
            # with open(book_json_path, "r", encoding="utf-8") as f:
            #     try:
            #         book_data = json.load(f)
            #     except json.JSONDecodeError as jde:
            #         logger.error(f"JSON decode error for file {book_json_path}: {jde}")
            #         continue  # Skip this book

            # Validate required fields
            if "book_title" not in book_data:
                continue  # Skip if title is missing

            # TODO: deprecated, delete after testing:
            # Assign a UUID if not present
            # if "book_id" not in book_data:
            #     book_data["book_id"] = str(uuid4())
            #     # Save the updated JSON back to the file
            #     with open(book_json_path, "w", encoding="utf-8") as f_out:
            #         json.dump(book_data, f_out, indent=4)
            #     logger.info(f"Assigned new UUID to book '{book_data['book_title']}'.")

            books_list.append(
                {"book_id": str(book_data["book_id"]), "title": book_data["book_title"]}
            )
        # sort the books by title, alphabetically
        # assumed to be O(nlog⁡n)O(nlogn) for time and O(n) for space
        # (could be dangerous!)
        sorted_books = sorted(books_list, key=lambda x: x["title"])
        return sorted_books

    except Exception as e:
        logger.exception(f"Unexpected error listing books: {e}")
        raise HTTPException(status_code=500, detail="Error listing books.")


@router.get("/{book_id}/", response_model=BookResponse)
async def get_book_by_id(book_id: str):
    """
    Fetches a specific book by its ID.
    """
    logger.info(f"Received request to fetch book with ID: {book_id}")
    try:
        # Determine the absolute path to the local_data directory
        current_file = Path(__file__).resolve()
        local_data_path = current_file.parents[3] / "local_data"

        if not local_data_path.exists():
            logger.error(f"local_data directory not found at {local_data_path}")
            raise HTTPException(
                status_code=500, detail="local_data directory not found."
            )

        # Iterate over book directories to find the book with matching ID
        book_dirs = [d for d in local_data_path.iterdir() if d.is_dir()]

        for book_dir in book_dirs:
            json_files = [f for f in book_dir.iterdir() if f.suffix == ".json"]
            if not json_files:
                continue
            book_json_path = json_files[0]

            try:
                book_data = read_json_file(book_json_path, "books")
            except Exception as e:
                logger.error(f"Error reading JSON for file {book_json_path}: {e}")

            # TODO: deprecated, delete after testing:
            # with open(book_json_path, "r", encoding="utf-8") as f:
            #     try:
            #         book_data = json.load(f)
            #     except json.JSONDecodeError as jde:
            #         logger.error(f"JSON decode error for file {book_json_path}: {jde}")
            #         continue

            if str(book_data.get("book_id", "")) == book_id:
                # Parse the book data
                book = Book(**book_data)

                # Transform the data to match BookResponse
                response = {
                    "book_id": str(book.book_id),
                    "title": book.book_title,
                    "pages": [
                        {
                            "page_number": page.page_number,
                            "text_content": page.content.text_content_of_this_page,
                            "illustration_b64_data": page.content.illustration_b64_data,
                            "characters": page.content.characters_in_this_page,
                        }
                        for page in book.pages
                    ],
                }

                book_response = BookResponse(**response)
                logger.info(f"Successfully fetched book '{book.book_title}'.")
                return book_response

        logger.error(f"Book with ID {book_id} not found.")
        raise HTTPException(status_code=404, detail="Book not found.")

    except Exception as e:
        logger.exception(f"Unexpected error fetching book: {e}")
        raise HTTPException(status_code=500, detail="Error fetching book.")
