# backend/src/main.py
from config import settings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import books


app = FastAPI(title="Kwento API", version="1.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust origins as necessary
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(books.router, prefix="/books", tags=["books"])
