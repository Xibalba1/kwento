# Kwento

Kwento is a full-stack application for generating illustrated children's books from a theme. The repository contains a FastAPI backend for story and image generation, storage, and book retrieval, plus a React frontend for browsing and creating books.

## Overview

- `backend/`: FastAPI API for generating, storing, and serving books
- `frontend/`: React application for creating and viewing books

## Tech Stack

- Backend: Python 3.11, FastAPI, Poetry, Pydantic
- Frontend: React 18, Create React App
- AI providers: Google GenAI and OpenAI
- Storage: Google Cloud Storage

## Repository Structure

```text
.
|-- backend/
|   |-- src/
|   `-- tests/
|-- frontend/
`-- README.md
```

## Prerequisites

- Python 3.11
- Poetry
- Node.js and npm
- API credentials for the configured AI provider
- Google Cloud Storage credentials

## Getting Started

### 1. Backend

Create `backend/src/.env` with the required configuration:

```env
OPENAI_API_KEY=your_openai_key
GOOGLE_GENAI_API_KEY=your_google_genai_key
GCS_API_KEY_JSON_B64=base64_encoded_service_account_json
GCS_BUCKET_NAME=your_bucket_name
```

Install dependencies and start the API:

```bash
cd backend
poetry install
cd src
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend runs at `http://localhost:8000`.

### 2. Frontend

Install dependencies and start the app:

```bash
cd frontend
npm install
npm start
```

The frontend runs at `http://localhost:3000`.

To point the frontend at a different backend, set `REACT_APP_API_BASE_URL`.

## Testing

Backend:

```bash
cd backend
poetry run pytest
```

Frontend:

```bash
cd frontend
npm test
```

## API Summary

The backend exposes book-focused endpoints under `/books`, including:

- `POST /books/` to generate a new book
- `GET /books/` to list books
- `GET /books/{book_id}/` to fetch a single book
- `GET /books/random/` to fetch a random book

## Notes

- The backend currently forces cloud storage mode and expects Google Cloud Storage credentials.
- CORS is open for development and should be tightened for production deployments.
- Additional service-specific details live in [backend/README.md](/Users/ik/repos/kwento/backend/README.md) and [frontend/README.md](/Users/ik/repos/kwento/frontend/README.md).
