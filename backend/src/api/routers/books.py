# backend/src/kwento_backend/api/routers/books.py

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import logging

from api.models.book_models import Book
from core import content_generation

router = APIRouter()
logger = logging.getLogger(__name__)


class BookCreateRequest(BaseModel):
    theme: str


class PageResponse(BaseModel):
    page_number: int
    text_content: str
    illustration_data: str
    characters: List[str]


class BookResponse(BaseModel):
    book_id: str
    title: str
    pages: List[dict]


@router.post("/", response_model=BookResponse)
async def create_book(book_request: BookCreateRequest):
    try:
        book = await content_generation.generate_book(book_request.theme)
        response = BookResponse(
            book_id=str(id(book)),
            title=book.book_title,
            pages=[
                PageResponse(
                    page_number=page.page_number,
                    text_content=page.content.text_content_of_this_page,
                    illustration_data=page.content.illustration_b64_data,
                    characters=page.content.characters_in_this_page,
                )
                for page in book.pages
            ],
        )
        return response
    except Exception as e:
        logger.error(f"Error creating book: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating book: {e}")
