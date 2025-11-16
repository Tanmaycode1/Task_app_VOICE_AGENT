"""Database initialization utilities."""

from app.db.base import Base, engine
from app.models import ConversationMessage, Task  # noqa: F401 - ensures models are registered


def init_db() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


if __name__ == "__main__":
    init_db()

