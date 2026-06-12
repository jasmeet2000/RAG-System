"""
Application configuration using Pydantic Settings.

=== WHY THIS FILE EXISTS ===
Every production application needs centralized configuration management.
This file is the SINGLE SOURCE OF TRUTH for all settings in the application.
It replaces scattered os.getenv() calls with a type-safe, validated, and
documented configuration system.

=== HOW IT WORKS ===
1. Pydantic Settings reads from .env file and environment variables.
2. Environment variables ALWAYS override .env file values (12-factor app principle).
3. All values are type-checked at startup — if QDRANT_PORT="abc", the app
   crashes immediately with a clear error instead of failing silently later.
4. Other modules import `settings` singleton: `from app.core.config import settings`

=== WHAT HAPPENS WITHOUT IT ===
- Configuration scattered across files via os.getenv()
- No type validation (port numbers as strings, booleans as "true"/"false")
- No defaults documentation — you'd need to grep the entire codebase
- Secrets accidentally hardcoded in source files

=== INDUSTRY ALTERNATIVES ===
- dynaconf: More features (multiple environments, vaults), more complexity
- python-decouple: Simpler but no type validation
- Hydra (Facebook): YAML-based, great for ML experiments, overkill for APIs
- AWS SSM / HashiCorp Vault: For production secrets management (we use .env for dev)
"""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# Project root directory — resolved relative to this file's location
# config.py is at: rag-system/app/core/config.py
# Project root is: rag-system/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.

    Pydantic Settings v2 features used here:
    - model_config: Replaces the inner Config class (Pydantic v1 pattern)
    - Field(description=...): Self-documenting configuration
    - Type coercion: "8000" → 8000, "true" → True automatically
    - Validation: Invalid values crash at startup, not at runtime

    Usage:
        from app.core.config import settings
        print(settings.QDRANT_HOST)  # "localhost"
    """

    model_config = SettingsConfigDict(
        # Load from .env file in project root
        env_file=str(PROJECT_ROOT / ".env"),
        # .env file is optional — environment variables work without it
        env_file_encoding="utf-8",
        # Environment variables are case-insensitive
        case_sensitive=False,
        # Extra fields in .env are ignored (not errors)
        extra="ignore",
    )

    # ── Application Settings ────────────────────────────────────────────
    APP_NAME: str = Field(
        default="RAG System",
        description="Application name displayed in API docs and logs.",
    )
    APP_VERSION: str = Field(
        default="0.1.0",
        description="Semantic version of the application.",
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode. NEVER True in production.",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )

    # ── API Settings ────────────────────────────────────────────────────
    API_HOST: str = Field(
        default="0.0.0.0",
        description="Host to bind the FastAPI server.",
    )
    API_PORT: int = Field(
        default=8000,
        description="Port to bind the FastAPI server.",
    )
    API_RELOAD: bool = Field(
        default=True,
        description="Enable auto-reload for development. Disable in production.",
    )

    # ── Qdrant Settings ─────────────────────────────────────────────────
    QDRANT_HOST: str = Field(
        default="localhost",
        description="Qdrant server hostname.",
    )
    QDRANT_PORT: int = Field(
        default=6333,
        description="Qdrant REST API port.",
    )
    QDRANT_GRPC_PORT: int = Field(
        default=6334,
        description="Qdrant gRPC port (faster for large operations).",
    )
    QDRANT_COLLECTION_NAME: str = Field(
        default="documents",
        description="Default Qdrant collection name for document vectors.",
    )

    # ── Embedding Settings ──────────────────────────────────────────────
    EMBEDDING_MODEL_NAME: str = Field(
        default="all-MiniLM-L6-v2",
        description=(
            "Sentence-Transformers model for generating embeddings. "
            "Options: all-MiniLM-L6-v2, BAAI/bge-small-en-v1.5, BAAI/bge-base-en-v1.5"
        ),
    )
    EMBEDDING_DIMENSION: int = Field(
        default=384,
        description="Dimension of the embedding vectors. Must match the model.",
    )
    EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        description="Batch size for embedding generation. Larger = faster but more RAM.",
    )

    # ── Chunking Settings ───────────────────────────────────────────────
    CHUNK_SIZE: int = Field(
        default=512,
        description="Target chunk size in characters.",
    )
    CHUNK_OVERLAP: int = Field(
        default=50,
        description="Overlap between consecutive chunks in characters.",
    )
    CHUNKING_STRATEGY: str = Field(
        default="recursive",
        description="Chunking strategy: fixed, recursive, semantic, parent_child.",
    )

    # ── Ollama Settings ─────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL.",
    )
    OLLAMA_MODEL: str = Field(
        default="llama3.1:8b",
        description="Default Ollama model for generation.",
    )
    OLLAMA_TIMEOUT: int = Field(
        default=120,
        description="Timeout in seconds for Ollama API calls.",
    )
    OLLAMA_TEMPERATURE: float = Field(
        default=0.1,
        description=(
            "LLM temperature. Lower = more deterministic. "
            "0.1 is good for RAG (factual answers)."
        ),
    )

    # ── Retrieval Settings ──────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = Field(
        default=20,
        description="Number of candidates to retrieve before re-ranking.",
    )
    RERANK_TOP_K: int = Field(
        default=5,
        description="Number of final results after re-ranking.",
    )
    RERANKER_MODEL: str = Field(
        default="BAAI/bge-reranker-base",
        description="Cross-encoder model for re-ranking.",
    )

    # ── Data Paths ──────────────────────────────────────────────────────
    DATA_DIR: Path = Field(
        default=PROJECT_ROOT / "data",
        description="Root data directory.",
    )
    RAW_DATA_DIR: Path = Field(
        default=PROJECT_ROOT / "data" / "raw",
        description="Directory for raw input documents.",
    )
    PROCESSED_DATA_DIR: Path = Field(
        default=PROJECT_ROOT / "data" / "processed",
        description="Directory for processed/cached data.",
    )

    @property
    def qdrant_url(self) -> str:
        """Construct the full Qdrant REST API URL."""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.DEBUG


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Create and cache a Settings instance.

    Why @lru_cache?
    - Settings are read-only after startup. No need to re-parse .env every call.
    - Guarantees all modules see the SAME settings instance.
    - This is the "poor man's singleton" — simple and Pythonic.

    Why a function instead of a module-level variable?
    - Testability: In tests, you can override this with dependency injection.
    - FastAPI's Depends() system works with callables, not variables.
    """
    return Settings()


# Module-level convenience — import this in most modules
settings = get_settings()
