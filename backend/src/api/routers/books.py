# backend/src/api/routers/books.py

import random
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone

from utils.general_utils import get_logger
from config import settings
from api.models.book_models import (
    Book,
    BookResponse,
    BookCreateRequest,
    ArchiveBookRequest,
    CoverResponse,
    ImageResponse,
)
from core import content_generation
from core.generation_errors import (
    BookGenerationTimeoutError,
    StoryGenerationTimeoutError,
)
from utils.general_utils import (
    get_book_list,
    get_book_by_id,
    read_json_file,
    generate_presigned_url,
    save_book_library_state,
)


from utils.general_utils import get_logger

router = APIRouter()


logger = get_logger(__name__)


@router.post("/", response_model=BookResponse)
async def create_book(book_request: BookCreateRequest):
    """
    Endpoint to create a new book based on a given theme.
    """
    request_id = str(uuid4())
    logger.info(f"Received request to create book with theme: '{book_request.theme}'")
    try:
        book = await content_generation.generate_book(
            book_request.theme, request_id=request_id
        )
        logger.info(
            f"Generated book titled: '{book.book_title}' with {len(book.pages)} pages."
        )

        # Generate pre-signed URL for the book JSON file
        expiration_time = timedelta(hours=1)
        expires_at = datetime.now(timezone.utc) + expiration_time

        if settings.use_cloud_storage:
            json_blob_name = f"{book.book_id}/{book.book_id}.json"
            json_url = generate_presigned_url(json_blob_name, expiration=3600)
        else:
            json_url = str(
                (
                    Path(settings.local_data_path)
                    / f"{book.book_id}/{book.book_id}.json"
                ).resolve()
            )

        # Prepare the response
        images_response = []
        for page in book.pages:
            illustration = page.content.illustration
            if illustration:
                images_response.append(
                    ImageResponse(
                        page=page.page_number,
                        url=illustration["url"],
                        expires_at=illustration["expires_at"],
                    )
                )
            else:
                logger.warning(f"No illustration data for page {page.page_number}")

        response = BookResponse(
            book_id=str(book.book_id),
            book_title=book.book_title,
            expires_at=expires_at,
            json_url=json_url,
            is_archived=False,
            cover=(
                CoverResponse(
                    url=book.cover["url"],
                    expires_at=book.cover["expires_at"],
                    provider=book.cover.get("provider"),
                    model=book.cover.get("model"),
                )
                if isinstance(book.cover, dict)
                else None
            ),
            images=images_response,
        )

        logger.info(f"Successfully constructed response for book: {book.book_title}")
        return response
    except StoryGenerationTimeoutError as exc:
        logger.warning(
            "Story generation timed out. request_id=%s stage=%s provider=%s model=%s elapsed_seconds=%s timeout_seconds=%s",
            request_id,
            exc.stage,
            exc.provider,
            exc.model,
            exc.elapsed_seconds,
            exc.timeout_seconds,
        )
        return JSONResponse(
            status_code=504,
            content={
                "detail": "Story generation timed out",
                "request_id": request_id,
            },
        )
    except BookGenerationTimeoutError as exc:
        logger.warning(
            "Book generation timed out. request_id=%s stage=%s provider=%s model=%s elapsed_seconds=%s timeout_seconds=%s",
            request_id,
            exc.stage,
            exc.provider,
            exc.model,
            exc.elapsed_seconds,
            exc.timeout_seconds,
        )
        return JSONResponse(
            status_code=504,
            content={
                "detail": "Book generation timed out",
                "request_id": request_id,
            },
        )
    except ValueError as ve:
        if str(ve) == "Content policy violation":
            raise HTTPException(
                status_code=400,
                detail="The content of your request violates our content policy. Please try a different theme.",
            )
        logger.exception(
            "Book creation failed due to value error. request_id=%s error_type=%s error=%s",
            request_id,
            type(ve).__name__,
            str(ve),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Book creation failed. request_id={request_id}",
        )
    except Exception as e:
        logger.exception(
            "Failed to create book. request_id=%s error_type=%s error=%s",
            request_id,
            type(e).__name__,
            str(e),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Book creation failed. request_id={request_id}",
        )


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
        json_files = [
            f
            for f in selected_book_dir.iterdir()
            if f.suffix == ".json" and f.name == f"{selected_book_dir.name}.json"
        ]
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

        # Validate required fields
        required_fields = ["book_title", "pages"]
        for field in required_fields:
            if field not in book_data:
                logger.error(f"Missing required field '{field}' in {book_json_path}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Missing required field '{field}' in book data.",
                )

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
                "book_id": str(book.book_id),
                "title": book.book_title,
                "pages": [
                    {
                        "page_number": page.page_number,
                        "text_content": page.content.text_content_of_this_page,
                        "illustration": page.content.illustration,  # Use the illustration URL
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
async def list_books(request: Request):
    """
    Lists all existing books with metadata, pre-signed URLs, and images.
    """
    logger.info("Received request to list all books.")
    try:
        books_list = get_book_list()

        if not books_list:
            logger.error("No books available.")
            raise HTTPException(status_code=404, detail="No books available.")

        sorted_books = sorted(books_list, key=lambda x: x["book_title"])
        logger.debug(f"list_books(): book list sorted. returning `sorted_books`")
        return sorted_books

    except Exception as e:
        logger.exception(f"Unexpected error listing books: {e}")
        raise HTTPException(status_code=500, detail="Error listing books.")


@router.get("/{book_id}/", response_model=BookResponse)
async def fetch_book_by_id(book_id: str):
    """
    Fetches a specific book by its ID.
    """
    logger.info(f"Received request to fetch book with ID: {book_id}")
    try:
        book = get_book_by_id(book_id)  # Call the utility function
        return book
    except ValueError as e:
        logger.error(str(e))
        raise HTTPException(status_code=404, detail="Book not found.")
    except Exception as e:
        logger.exception(f"Unexpected error fetching book: {e}")
        raise HTTPException(status_code=500, detail="Error fetching book.")


@router.patch("/{book_id}/archive/", response_model=BookResponse)
async def update_book_archive_state(book_id: str, archive_request: ArchiveBookRequest):
    """
    Updates archive state for a specific book.
    """
    logger.info(
        "Received request to update archive state for book_id=%s is_archived=%s",
        book_id,
        archive_request.is_archived,
    )
    try:
        get_book_by_id(book_id)
        save_book_library_state(book_id, archive_request.is_archived)
        return get_book_by_id(book_id)
    except ValueError as e:
        logger.error(str(e))
        raise HTTPException(status_code=404, detail="Book not found.")
    except Exception as e:
        logger.exception(
            "Unexpected error updating archive state for book_id=%s: %s",
            book_id,
            e,
        )
        raise HTTPException(status_code=500, detail="Error updating archive state.")
