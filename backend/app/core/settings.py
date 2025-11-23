"""Application settings and configuration utilities."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Immutable application settings derived from environment variables."""

    project_name: str = os.getenv("PROJECT_NAME", "Shram AI Backend")
    version: str = os.getenv("PROJECT_VERSION", "0.1.0")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    environment: str = os.getenv("ENVIRONMENT", "local")
    deepgram_api_key: str | None = os.getenv("DEEPGRAM_API_KEY")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    
    # LLM Provider Configuration
    use_groq: bool = os.getenv("USE_GROQ", "false").lower() == "true"
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    @property
    def database_path(self) -> str:
        """Return path to SQLite database file."""
        db_path = os.getenv("DATABASE_PATH")
        if db_path:
            return db_path
        # Default: shram.db in backend directory
        backend_dir = Path(__file__).parent.parent.parent
        return str(backend_dir / "shram.db")


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()

