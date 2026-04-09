import { DEFAULT_SORT, SORT_FIELDS, cycleSort, sortBooks } from "./bookSorting";

describe("bookSorting", () => {
  test("sorts titles case-insensitively, punctuation-insensitively, and numerically", () => {
    const books = [
      { book_id: "book-c", book_title: "Book 10" },
      { book_id: "book-a", book_title: "Alpha!" },
      { book_id: "book-b", book_title: "Book 2" },
      { book_id: "book-d", book_title: "alpha" },
    ];

    expect(sortBooks(books, DEFAULT_SORT).map((book) => book.book_id)).toEqual([
      "book-a",
      "book-d",
      "book-b",
      "book-c",
    ]);
  });

  test("sorts created_at values oldest first and newest first", () => {
    const books = [
      { book_id: "book-2", book_title: "Beta", created_at: "2026-04-09T10:00:00Z" },
      { book_id: "book-1", book_title: "Alpha", created_at: "2026-04-08T10:00:00Z" },
      { book_id: "book-3", book_title: "Gamma", created_at: "2026-04-10T10:00:00Z" },
    ];

    expect(
      sortBooks(books, { field: SORT_FIELDS.CREATED, direction: "asc" }).map((book) => book.book_id),
    ).toEqual(["book-1", "book-2", "book-3"]);

    expect(
      sortBooks(books, { field: SORT_FIELDS.CREATED, direction: "desc" }).map((book) => book.book_id),
    ).toEqual(["book-3", "book-2", "book-1"]);
  });

  test("sorts missing or invalid created_at values last", () => {
    const books = [
      { book_id: "book-3", book_title: "Gamma", created_at: null },
      { book_id: "book-1", book_title: "Alpha", created_at: "2026-04-08T10:00:00Z" },
      { book_id: "book-2", book_title: "Beta", created_at: "not-a-date" },
    ];

    expect(
      sortBooks(books, { field: SORT_FIELDS.CREATED, direction: "asc" }).map((book) => book.book_id),
    ).toEqual(["book-1", "book-2", "book-3"]);
  });

  test("uses book_id as the tie breaker", () => {
    const books = [
      { book_id: "book-b", book_title: "Same Title" },
      { book_id: "book-a", book_title: "Same Title" },
    ];

    expect(sortBooks(books, DEFAULT_SORT).map((book) => book.book_id)).toEqual(["book-a", "book-b"]);
  });

  test("cycles sort state according to the product rules", () => {
    expect(cycleSort(DEFAULT_SORT, SORT_FIELDS.TITLE)).toEqual({ field: SORT_FIELDS.TITLE, direction: "desc" });
    expect(cycleSort({ field: SORT_FIELDS.TITLE, direction: "desc" }, SORT_FIELDS.TITLE)).toEqual(DEFAULT_SORT);
    expect(cycleSort(DEFAULT_SORT, SORT_FIELDS.CREATED)).toEqual({ field: SORT_FIELDS.CREATED, direction: "asc" });
    expect(cycleSort({ field: SORT_FIELDS.CREATED, direction: "asc" }, SORT_FIELDS.CREATED)).toEqual({
      field: SORT_FIELDS.CREATED,
      direction: "desc",
    });
    expect(cycleSort({ field: SORT_FIELDS.CREATED, direction: "desc" }, SORT_FIELDS.CREATED)).toEqual(DEFAULT_SORT);
  });
});
