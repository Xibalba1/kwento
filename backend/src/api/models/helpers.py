# backend/src/api/models/helpers.py

from .book_models import Book
from utils.general_utils import get_logger

logger = get_logger(__name__)


def assign_book_model_relationships(book: Book) -> Book:
    try:
        if not book or not isinstance(book, Book):
            raise TypeError(f"Expected type Book, but received type {type(book)}")
        for page in book.pages:
            page.assign_book_parent(book)
            if not page.content:
                raise ValueError(f"Page {page.page_number} has no content.")
            page.content.assign_page_parent(page)
            page.content.characters_in_this_page_data = [
                char_info
                for page_char in page.content.characters_in_this_page
                for char_info in book.characters
                if char_info.name == page_char
            ]
        logger.info(
            "Relationships successfully established for the entire book structure."
        )
    except Exception as e:
        logger.exception("An error occurred while assigning relationships.")
        raise
    return book


def remove_book_model_relationships(book: Book) -> Book:
    try:
        for page in book.pages:
            page.remove_book_parent()
            if not page.content:
                raise ValueError(f"Page {page.page_number} has no content.")
            page.content.remove_page_parent()
            page.content.characters_in_this_page_data = []
        logger.info("Relationships successfully removed for the entire book structure.")
    except Exception as e:
        logger.exception("An error occurred while removing relationships.")
        raise
    return book
