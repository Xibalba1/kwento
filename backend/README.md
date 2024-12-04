# Instructions (Local Testing)

From terminal:

1. cd into `kwento/backend/src`
2. `poetry shell`
3. `uvicorn main:app --reload`

# TO DOs:

⃞ Prepare for deployment to Vercel  
✅ `backend/src/api/routers/books.py::create_book()` assigns an `id` to a book. This is not good.  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;✅ Instead, we should assign an `id` (`uuid`) to the book at creation time, and eliminate this assignment at delivery time.
