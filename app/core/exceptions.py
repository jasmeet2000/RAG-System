"""
Custom exception classes for the RAG system.

=== WHY THIS FILE EXISTS ===
Generic exceptions (ValueError, RuntimeError) tell you WHAT failed but not
WHERE in the pipeline or HOW to recover. Custom exceptions create a taxonomy
of failure modes that lets you:
1. Catch specific errors at the right layer
2. Map errors to appropriate HTTP status codes
3. Provide meaningful error messages to API consumers
4. Log errors with proper context

=== HOW IT INTERACTS WITH OTHER MODULES ===
- Raised by: ingestion, embeddings, vectordb, retrieval, generation modules
- Caught by: API layer (converts to HTTP responses), pipeline orchestrator
- Logged by: Each module logs the error before raising

=== WHAT HAPPENS WITHOUT IT ===
- All errors are generic ValueError/RuntimeError
- API layer can't distinguish "document not found" from "Qdrant is down"
- Error messages leak internal implementation details to API consumers
- No structured error handling strategy

=== INDUSTRY ALTERNATIVES ===
- HTTP exceptions only (FastAPI's HTTPException): Couples business logic to HTTP
- Result types (returns.Result): Functional approach, avoids exceptions entirely
- Error codes enum: Used alongside exceptions for machine-readable error types
"""

from typing import Optional

class RAGSystemError(Exception):
    """
    Base exception for all RAG system errors.

    All custom exceptions inherit from this class, enabling:
    - `except RAGSystemError` to catch any application error
    - Distinguishing our errors from Python built-in errors
    - Adding common attributes (error codes, context) in one place

    This is the "Exception Hierarchy" pattern — standard in production Python.
    """

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(self.message)


# ── Ingestion Errors ────────────────────────────────────────────────────


class DocumentLoadError(RAGSystemError):
    """Raised when a document cannot be loaded or parsed.

    Examples:
    - Corrupted PDF file
    - Unsupported file format
    - File not found
    - Encoding issues
    """

    pass


class ChunkingError(RAGSystemError):
    """Raised when text chunking fails.

    Examples:
    - Empty document after cleaning
    - Invalid chunk size configuration
    - Chunking strategy not found
    """

    pass


# ── Embedding Errors ────────────────────────────────────────────────────


class EmbeddingError(RAGSystemError):
    """Raised when embedding generation fails.

    Examples:
    - Model not found or failed to load
    - Input text exceeds model's max token limit
    - Out of memory during batch embedding
    """

    pass


class EmbeddingModelNotFoundError(EmbeddingError):
    """Raised when the specified embedding model cannot be loaded."""

    pass


# ── Vector Database Errors ──────────────────────────────────────────────


class VectorDBError(RAGSystemError):
    """Base error for all vector database operations.

    Examples:
    - Connection refused (Qdrant is down)
    - Collection doesn't exist
    - Dimension mismatch
    """

    pass


class VectorDBConnectionError(VectorDBError):
    """Raised when cannot connect to the vector database."""

    pass


class CollectionNotFoundError(VectorDBError):
    """Raised when the requested collection doesn't exist."""

    pass


# ── Retrieval Errors ────────────────────────────────────────────────────


class RetrievalError(RAGSystemError):
    """Raised when document retrieval fails.

    Examples:
    - No results found
    - Search timeout
    - Invalid query format
    """

    pass


# ── Re-ranking Errors ──────────────────────────────────────────────────


class RerankingError(RAGSystemError):
    """Raised when re-ranking fails.

    Examples:
    - Re-ranker model failed to load
    - Empty candidate list
    - Score computation error
    """

    pass


# ── Generation Errors ──────────────────────────────────────────────────


class GenerationError(RAGSystemError):
    """Base error for LLM generation failures."""

    pass


class LLMConnectionError(GenerationError):
    """Raised when cannot connect to the LLM service (Ollama).

    Examples:
    - Ollama server not running
    - Connection timeout
    - Model not pulled
    """

    pass


class LLMGenerationError(GenerationError):
    """Raised when LLM generation fails after connecting.

    Examples:
    - Context too long for model
    - Generation timeout
    - Invalid response format
    """

    pass


# ── Pipeline Errors ─────────────────────────────────────────────────────


class RAGPipelineError(RAGSystemError):
    """Raised when the end-to-end RAG pipeline fails.

    This wraps lower-level errors with pipeline context, such as
    which stage failed and what the input query was.
    """

    def __init__(
        self,
        message: str,
        stage: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        self.stage = stage
        super().__init__(message, detail)

    def __str__(self) -> str:
        if self.stage:
            return f"[Pipeline:{self.stage}] {self.message}"
        return self.message
