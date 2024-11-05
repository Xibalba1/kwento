"""
book_models.py
==============

This module defines the data models for the Kwento backend API, representing the core
entities involved in managing books, their pages, characters, and associated content.
Utilizing Pydantic's `BaseModel`, the module ensures data validation, type checking,
and provides utility methods for managing relationships between different entities.

Classes:
    - Character: Represents a character within a book, detailing their name, description,
      and appearance.
    - PageContent: Encapsulates the content of a single page, including textual content,
      illustrations, and the characters present on that page. It also manages the relationship
      to its parent `Page`.
    - Page: Represents an individual page in a book, containing `PageContent` and referencing
      its parent `Book`. It includes methods to assign or remove its parent `Book`.
    - Book: Represents a complete book, comprising multiple `Page` instances, a list of
      `Character` instances, and additional metadata such as title, synopsis, and illustration
      style. It provides methods to add or remove pages while maintaining data integrity.

Key Features:
    - **Data Validation**: Ensures that all fields adhere to the expected types and constraints
      using Pydantic validators. For example, page numbers and book lengths are validated to
      be positive integers.
    - **Relationship Management**: Provides methods to assign and remove parent relationships
      between `PageContent` and `Page`, as well as between `Page` and `Book`, ensuring referential
      integrity.
    - **Logging**: Implements detailed logging for operations such as assignments, additions,
      removals, and validation errors. This facilitates easier debugging and monitoring of
      the application's behavior.
    - **Error Handling**: Incorporates comprehensive error and exception handling to manage
      invalid data inputs and operational errors gracefully, raising appropriate exceptions
      and logging error messages.

Usage:
    The models defined in this module are intended to be used as part of the Kwento backend
    API for managing book-related data. They can be instantiated, validated, and manipulated
    as per the application's requirements, ensuring consistent and reliable data handling.

Example:
    ```python
    from book_models import Book, Page, PageContent, Character

    # Create characters
    hero = Character(name="Aria", description="A brave protagonist.", appearance="Tall with flowing hair.")
    villain = Character(name="Drake", description="The antagonist of the story.", appearance="Short and stern.")

    # Create page content
    content = PageContent(
        text_content_of_this_page="Aria enters the dark forest.",
        illustration="forest_illustration.png",
        characters_in_this_page=["Aria"]
    )

    # Create a page
    page = Page(page_number=1, content=content)

    # Create a book
    book = Book(
        book_title="The Brave Aria",
        book_length_n_pages=100,
        characters=[hero, villain],
        plot_synopsis="A tale of bravery and adventure.",
        pages=[page],
        illustration_style="Watercolor"
    )
    ```
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import logging

logger = logging.getLogger(__name__)


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


class PageContent(BaseModel):
    """
    Represents the content of a single page in a book.

    Attributes:
        text_content_of_this_page (str): The textual content of the page.
        illustration (str): The illustration associated with the page.
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
    illustration: Optional[str] = None  # Path to the saved image
    illustration_image: Optional[bytes] = None  # Image bytes if needed
    illustration_b64_data: Optional[str] = None  # Base64 image data

    def assign_page_parent(self, page_parent: Page) -> None:
        """
        Assigns a parent Page to this PageContent.

        Args:
            page_parent (Page): The parent Page to assign.

        Raises:
            TypeError: If page_parent is not an instance of Page.
        """
        if not isinstance(page_parent, Page):
            logger.error("Attempted to assign a non-Page instance as page_parent.")
            raise TypeError("page_parent must be an instance of Page.")
        self.page_parent = page_parent
        logger.info(f"Assigned page_parent {page_parent.page_number} to PageContent.")

    def remove_page_parent(self) -> None:
        """
        Removes the parent Page from this PageContent.
        """
        if self.page_parent:
            logger.info(
                f"Removing page_parent {self.page_parent.page_number} from PageContent."
            )
        self.page_parent = None


class Page(BaseModel):
    """
    Represents a single page in a book.

    Attributes:
        page_number (int): The number of the page in the book.
        content (PageContent): The content of the page.
        book_parent (Optional[Book]): Reference to the parent Book.
    """

    page_number: int
    content: PageContent
    book_parent: Optional[Book] = Field(default=None, exclude=True)

    def assign_book_parent(self, book_parent: Book) -> None:
        """
        Assigns a parent Book to this Page.

        Args:
            book_parent (Book): The parent Book to assign.

        Raises:
            TypeError: If book_parent is not an instance of Book.
        """
        if not isinstance(book_parent, Book):
            logger.error("Attempted to assign a non-Book instance as book_parent.")
            raise TypeError("book_parent must be an instance of Book.")
        self.book_parent = book_parent
        logger.info(
            f"Assigned book_parent '{book_parent.book_title}' to Page {self.page_number}."
        )

    def remove_book_parent(self) -> None:
        """
        Removes the parent Book from this Page.
        """
        if self.book_parent:
            logger.info(
                f"Removing book_parent '{self.book_parent.book_title}' from Page {self.page_number}."
            )
        self.book_parent = None

    @validator("page_number")
    def validate_page_number(cls, v: int) -> int:
        """
        Validates that the page number is positive.

        Args:
            v (int): The page number.

        Raises:
            ValueError: If the page number is not positive.

        Returns:
            int: The validated page number.
        """
        if v <= 0:
            logger.error("Page number must be positive.")
            raise ValueError("page_number must be a positive integer.")
        return v


class Book(BaseModel):
    """
    Represents a book.

    Attributes:
        book_title (str): The title of the book.
        book_length_n_pages (int): The number of pages in the book.
        characters (List[Character]): List of characters in the book.
        plot_synopsis (str): The plot synopsis of the book.
        pages (List[Page]): List of pages in the book.
        illustration_style (Optional[str]): The illustration style of the book.
    """

    book_title: str
    book_length_n_pages: int
    characters: List[Character] = Field(default_factory=list)
    plot_synopsis: str
    pages: List[Page] = Field(default_factory=list)
    illustration_style: Optional[Dict[str, Any]] = None

    @validator("book_length_n_pages")
    def validate_book_length(cls, v: int) -> int:
        """
        Validates that book_length_n_pages is positive.

        Args:
            v (int): The number of pages.

        Raises:
            ValueError: If the number of pages is not positive.

        Returns:
            int: The validated number of pages.
        """
        if v <= 0:
            logger.error("book_length_n_pages must be positive.")
            raise ValueError("book_length_n_pages must be a positive integer.")
        return v

    @validator("pages", each_item=True)
    def validate_pages(cls, page: Page, values: dict) -> Page:
        """
        Ensures that each page's book_parent is assigned to this book.

        Args:
            page (Page): The page being validated.
            values (dict): The other fields of the model.

        Raises:
            ValueError: If book_parent of the page does not match this book.

        Returns:
            Page: The validated page.
        """
        if (
            "book_title" in values
            and page.book_parent
            and page.book_parent.book_title != values["book_title"]
        ):
            logger.error("Page's book_parent does not match the book's title.")
            raise ValueError("Page's book_parent does not match the book's title.")
        return page

    def add_page(self, page: Page) -> None:
        """
        Adds a page to the book.

        Args:
            page (Page): The page to add.

        Raises:
            TypeError: If page is not an instance of Page.
            ValueError: If adding the page exceeds book_length_n_pages.
        """
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
        """
        Removes a page from the book by its page number.

        Args:
            page_number (int): The number of the page to remove.

        Raises:
            ValueError: If the page_number does not exist in the book.
        """
        page = next((p for p in self.pages if p.page_number == page_number), None)
        if not page:
            logger.error(
                f"Page number {page_number} not found in book '{self.book_title}'."
            )
            raise ValueError(f"Page number {page_number} not found in the book.")
        page.remove_book_parent()
        self.pages.remove(page)
        logger.info(f"Removed page {page_number} from book '{self.book_title}'.")


# Add the following lines to resolve forward references
PageContent.update_forward_refs()
Page.update_forward_refs()
Book.update_forward_refs()
