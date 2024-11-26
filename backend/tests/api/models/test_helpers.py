import pytest
from src.api.models.book_models import Book, Page, PageContent, Character
from src.api.models.helpers import assign_book_model_relationships


def test_assign_book_model_relationships():
    char = Character(
        name="Testy McTestface",
        description="A curious explorer",
        appearance="Tall with a big hat",
    )
    content = PageContent(
        text_content_of_this_page="Testy begins his journey.",
        characters_in_this_page=["Testy McTestface"],
    )
    page = Page(page_number=1, content=content)
    book = Book(
        book_title="The Adventures of Testy McTestface",
        book_length_n_pages=1,
        characters=[char],
        plot_synopsis="An exciting journey into the world of testing.",
        pages=[page],
    )

    assign_book_model_relationships(book)

    # Assertions
    assert page.book_parent == book
    assert content.page_parent == page
    assert len(content.characters_in_this_page_data) == 1
    assert content.characters_in_this_page_data[0].name == "Testy McTestface"
