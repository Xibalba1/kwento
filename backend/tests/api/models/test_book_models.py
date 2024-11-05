import pytest
from kwento_backend.api.models.book_models import Character, PageContent, Page, Book


def test_character_model():
    char = Character(
        name="Testy McTestface",
        description="A curious explorer",
        appearance="Tall with a big hat",
    )
    assert char.name == "Testy McTestface"


def test_page_content():
    content = PageContent(
        text_content_of_this_page="Testy begins his journey.",
        characters_in_this_page=["Testy McTestface"],
    )
    assert content.text_content_of_this_page == "Testy begins his journey."


def test_page_model():
    content = PageContent(
        text_content_of_this_page="Testy begins his journey.",
        characters_in_this_page=["Testy McTestface"],
    )
    page = Page(page_number=1, content=content)
    assert page.page_number == 1
    assert page.content.text_content_of_this_page == "Testy begins his journey."


def test_book_model():
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
    assert book.book_title == "The Adventures of Testy McTestface"
    assert book.pages[0].page_number == 1


def test_page_number_validation():
    with pytest.raises(ValueError):
        Page(
            page_number=0,
            content=PageContent(
                text_content_of_this_page="Invalid page number",
                characters_in_this_page=[],
            ),
        )


def test_book_length_validation():
    with pytest.raises(ValueError):
        Book(
            book_title="Invalid Book",
            book_length_n_pages=0,
            characters=[],
            plot_synopsis="",
            pages=[],
        )


def test_add_page_to_book():
    book = Book(
        book_title="Test Book",
        book_length_n_pages=1,
        characters=[],
        plot_synopsis="",
        pages=[],
    )
    content = PageContent(
        text_content_of_this_page="Page content", characters_in_this_page=[]
    )
    page = Page(page_number=1, content=content)
    book.add_page(page)
    assert len(book.pages) == 1

    with pytest.raises(ValueError):
        # Exceed book_length_n_pages
        another_page = Page(page_number=2, content=content)
        book.add_page(another_page)
