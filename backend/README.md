# Kwento Backend

FastAPI backend for generating children's books (story + illustrations), storing outputs, and serving book metadata to the frontend.

## Architecture Overview

### Entry Point
- `src/main.py`
- Creates the FastAPI app.
- Configures CORS.
- Mounts the books router at `/books`.

### API Layer
- `src/api/routers/books.py`
- Exposes endpoints to:
1. Create a new book.
2. List existing books.
3. Fetch a specific book by ID.
4. Fetch a random local book.

### Domain Models
- `src/api/models/book_models.py`
- Pydantic models for:
1. `BookCreateRequest` input (`theme`).
2. Core book entities (`Book`, `Page`, `PageContent`, `Character`).
3. API output (`BookResponse`, `ImageResponse`).

### Core Generation Flow
- `src/core/content_generation.py`
- Builds the master prompt from `src/core/prompts/prompts.py`.
- Calls OpenAI text generation (`services/openai_service.py`) to produce book JSON.
- Validates into `Book` model.
- Assigns model relationships.
- Chooses illustration style.
- Triggers illustration generation.

- `src/core/image_generation.py`
- Builds per-page illustration prompts.
- Calls OpenAI image generation for each page.
- Saves images via `services/image_service.py`.
- Persists final book JSON.

### Services Layer
- `src/services/openai_service.py`
- Handles OpenAI calls for:
1. Story JSON generation (`chat.completions`).
2. Illustration generation (`images.generate`).

- `src/services/image_service.py`
- Saves image binaries either:
1. To GCS (with presigned URLs), or
2. Locally (if cloud storage is disabled).

### Storage + Utilities
- `src/utils/general_utils.py`
- Central utilities for:
1. Logging.
2. Local file I/O.
3. GCS client initialization.
4. JSON read/write.
5. Presigned URL generation.
6. Book listing/fetching from storage.

### Runtime Configuration
- `src/config.py`
- Loads settings from environment / `.env`.
- Decodes `GCS_API_KEY_JSON_B64` to service-account JSON.
- Important: current code forces `settings.use_cloud_storage = True`, so GCS is required unless code is changed.

## Request Lifecycle (Create Book)

1. `POST /books/` receives `{ "theme": "..." }`.
2. Router calls `content_generation.generate_book(theme)`.
3. Text model generates structured book JSON.
4. JSON is validated into `Book`.
5. Image model generates one illustration per page.
6. Images + JSON are stored (currently GCS by default).
7. API returns `BookResponse` with:
   - `book_id`
   - `book_title`
   - `json_url`
   - page image URLs with expiration metadata.

## API Endpoints

- `POST /books/` create book from theme.
- `GET /books/` list books.
- `GET /books/{book_id}/` fetch one book.
- `GET /books/random/` fetch random local book.

## Run Locally

### Prerequisites
- Python 3.11
- Poetry
- OpenAI API key
- GCS service account credentials encoded as base64 JSON

### Environment

Create `backend/src/.env`:

```env
OPENAI_API_KEY=your_openai_key
GCS_API_KEY_JSON_B64=base64_encoded_service_account_json
```

Optional variables (have defaults in code):

```env
LOCAL_DATA_PATH=local_data
GCS_BUCKET_NAME=kwento-books
```

### Start Server

From repo root:

```bash
cd backend
poetry install
cd src
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend URL: `http://localhost:8000`

## Run on Railway

`src/railway.json` defines:
- Build: `NIXPACKS`
- Start command: `hypercorn main:app --bind "[::]:$PORT"`

### Recommended Railway Setup

1. Create a Railway service from this repo.
2. Set the service root directory to `backend/src` so Railway can run `main.py` directly.
3. Add environment variables:
   - `OPENAI_API_KEY`
   - `GCS_API_KEY_JSON_B64`
   - `GCS_BUCKET_NAME` (if different from default)
4. Deploy.

### Notes

- If you keep service root at `backend` instead of `backend/src`, adjust start command/module path accordingly.
- In production, tighten CORS (`src/main.py`) instead of `allow_origins=["*"]`.
