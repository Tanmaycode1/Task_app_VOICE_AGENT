"""SQLAlchemy base and engine configuration."""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.settings import get_settings

settings = get_settings()

# Suppress SQLAlchemy engine logging (only show errors)
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)

# SQLite engine - creates file in backend directory
engine = create_engine(
    f"sqlite:///{settings.database_path}",
    connect_args={"check_same_thread": False},  # needed for SQLite
    echo=False,  # Disable SQL query logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


def get_db():
    """Dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

