# backend/src/main.py
import logging
from config import settings

logging.basicConfig(level=settings.logging_level)
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
