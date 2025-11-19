"""FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.settings import get_settings
from app.db.init_db import init_db

# Configure logging - suppress SQLAlchemy engine logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.pool").setLevel(logging.ERROR)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.ERROR)


def create_application() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.project_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    # CORS middleware for frontend
    # Allow all origins in development, specific origins in production
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://localhost:3000",
        "https://localhost:3001",
        "https://taskappforntend.vercel.app/",
    ]
    
    # For development/testing, allow all origins
    # Comment this out in production and use specific origins above
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for now
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    application.include_router(api_router, prefix=settings.api_prefix)

    @application.on_event("startup")
    async def startup_event():
        """Initialize database on startup."""
        init_db()

    return application


app = create_application()