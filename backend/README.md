# Instructions (Local Testing)

From terminal:

1. cd into `kwento/backend`
2. `poetry shell`
3. `uvicorn main:app --reload`

# TO DOs:

- `backend/src/kwento_backend/api/routers/books.py::create_book()` assigns an `id` to a book. This is not good.
  - Instead, we should assign an `id` (`uuid`) to the book at creation time, and eliminate this assignment at delivery time.
