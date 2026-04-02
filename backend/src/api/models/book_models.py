"""
This module defines the data models for the Kwento backend API, representing the core
entities involved in managing books, their pages, characters, and associated content.
Utilizing Pydantic's `BaseModel`, the module ensures data validation, type checking,
and provides utility methods for managing relationships between different entities.
"""

# backend/src/api/models/book_models.py

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from utils.general_utils import get_logger
from uuid import UUID, uuid4
from datetime import datetime


logger = get_logger(__name__)


class Character(BaseModel):
    """
    Represents a character in a book.

    Attributes:
        name (str): The name of the character.
        description (str): A description of the character.
        appearance (str): Details about the character's appearance.
    """

    name: str
    description: str
    appearance: str


class Setting(BaseModel):
    """
    Represents a reusable setting anchor for page illustrations.

    Attributes:
        id (str): Stable setting identifier (for example "S1").
        name (str): Human-readable setting label.
        visual_anchor_details (str): Visual details to keep setting depictions consistent.
    """

    id: str
    name: str
    visual_anchor_details: str


class PageContent(BaseModel):
    """
    Represents the content of a single page in a book.

    Attributes:
        text_content_of_this_page (str): The textual content of the page.
        illustration (Optional[str]): The URL or path to the saved image.
        characters_in_this_page (List[str]): List of character names appearing on the page.
        illustration_prompt (Optional[str]): Prompt for the illustration.
        illustration_prompt_system_revised (Optional[str]): Revised system prompt for the illustration.
        page_parent (Optional[Page]): Reference to the parent Page.
        characters_in_this_page_data (Optional[List[Character]]): Detailed data of characters on the page.
    """

    text_content_of_this_page: str
    characters_in_this_page: List[str] = Field(default_factory=list)
    page_parent: Optional[Page] = Field(default=None, exclude=True)
    characters_in_this_page_data: Optional[List[Character]] = None
    illustration_prompt: Optional[str] = None
    illustration_prompt_system_revised: Optional[str] = None
    illustration: Optional[str] = None  # URL or path to the saved image
    illustration_b64_data: Optional[str] = (
        None  # TODO: determine if this can be removed
    )

    def assign_page_parent(self, page_parent: Page) -> None:
        if not isinstance(page_parent, Page):
            logger.error("Attempted to assign a non-Page instance as page_parent.")
            raise TypeError("page_parent must be an instance of Page.")
        self.page_parent = page_parent
        logger.info(f"Assigned page_parent {page_parent.page_number} to PageContent.")

    def remove_page_parent(self) -> None:
        if self.page_parent:
            logger.info(
                f"Removing page_parent {self.page_parent.page_number} from PageContent."
            )
        self.page_parent = None


class Page(BaseModel):
    page_number: int
    setting_id: Optional[str] = None
    content: PageContent
    book_parent: Optional[Book] = Field(default=None, exclude=True)

    def assign_book_parent(self, book_parent: Book) -> None:
        if not isinstance(book_parent, Book):
            logger.error("Attempted to assign a non-Book instance as book_parent.")
            raise TypeError("book_parent must be an instance of Book.")
        self.book_parent = book_parent
        logger.info(
            f"Assigned book_parent '{book_parent.book_title}' to Page {self.page_number}."
        )

    def remove_book_parent(self) -> None:
        if self.book_parent:
            logger.info(
                f"Removing book_parent '{self.book_parent.book_title}' from Page {self.page_number}."
            )
        self.book_parent = None

    @validator("page_number")
    def validate_page_number(cls, v: int) -> int:
        if v <= 0:
            logger.error("Page number must be positive.")
            raise ValueError("page_number must be a positive integer.")
        return v


class Book(BaseModel):
    book_id: UUID = Field(default_factory=uuid4)
    book_title: str
    book_length_n_pages: int
    characters: List[Character] = Field(default_factory=list)
    settings: List[Setting] = Field(default_factory=list)
    plot_synopsis: str
    pages: List[Page] = Field(default_factory=list)
    cover: Optional[Dict[str, Any]] = None
    illustration_style: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
        }

    @validator("book_length_n_pages")
    def validate_book_length(cls, v: int) -> int:
        if v <= 0:
            logger.error("book_length_n_pages must be positive.")
            raise ValueError("book_length_n_pages must be a positive integer.")
        return v

    @validator("pages", each_item=True)
    def validate_pages(cls, page: Page, values: dict) -> Page:
        if (
            "book_title" in values
            and page.book_parent
            and page.book_parent.book_title != values["book_title"]
        ):
            logger.error("Page's book_parent does not match the book's title.")
            raise ValueError("Page's book_parent does not match the book's title.")
        return page

    def add_page(self, page: Page) -> None:
        if not isinstance(page, Page):
            logger.error("Attempted to add a non-Page instance to book.")
            raise TypeError("page must be an instance of Page.")
        if len(self.pages) >= self.book_length_n_pages:
            logger.error("Cannot add page: book_length_n_pages limit reached.")
            raise ValueError("Cannot add more pages than book_length_n_pages.")
        page.assign_book_parent(self)
        self.pages.append(page)
        logger.info(f"Added page {page.page_number} to book '{self.book_title}'.")

    def remove_page(self, page_number: int) -> None:
        page = next((p for p in self.pages if p.page_number == page_number), None)
        if not page:
            logger.error(
                f"Page number {page_number} not found in book '{self.book_title}'."
            )
            raise ValueError(f"Page number {page_number} not found in the book.")
        page.remove_book_parent()
        self.pages.remove(page)
        logger.info(f"Removed page {page_number} from book '{self.book_title}'.")


class BookCreateRequest(BaseModel):
    theme: str


class ImageResponse(BaseModel):
    page: int
    url: str
    expires_at: datetime


class CoverResponse(BaseModel):
    url: str
    expires_at: datetime
    provider: Optional[str] = None
    model: Optional[str] = None


class BookResponse(BaseModel):
    book_id: str
    book_title: str
    expires_at: datetime  # Expiration timestamp for the JSON URL
    json_url: str  # Pre-signed URL for the book's JSON metadata
    cover: Optional[CoverResponse] = None
    is_archived: bool = False
    images: List[
        ImageResponse
    ]  # List of images with their URLs and expiration metadata


class ArchiveBookRequest(BaseModel):
    is_archived: bool


# Add the following lines to resolve forward references
PageContent.update_forward_refs()
Page.update_forward_refs()
Book.update_forward_refs()
