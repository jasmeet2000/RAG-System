"""
Application-wide constants.

=== WHY THIS FILE EXISTS ===
Constants are values that NEVER change between environments (dev, staging, prod).
They are different from configuration (config.py), which changes per environment.

Example:
- SUPPORTED_FILE_TYPES is always the same → constant (here)
- QDRANT_HOST varies per environment → config (.env)

Centralizing constants prevents magic strings/numbers scattered across the codebase.

=== HOW IT INTERACTS WITH OTHER MODULES ===
Imported by any module that needs fixed values:
    from app.core.constants import SUPPORTED_FILE_TYPES

=== WHAT HAPPENS WITHOUT IT ===
- Magic strings: ".pdf" hardcoded in 5 different files
- If you need to add ".epub" support, you'd need to find every hardcoded ".pdf"
- No documentation of what file types, strategies, or models are supported

=== INDUSTRY ALTERNATIVES ===
- Enum classes: More type-safe, but heavier for simple string lists
- Frozen dataclasses: Good for grouped constants
- Module-level constants: What we use — simple and Pythonic
"""

from typing import Final

# ── Supported Document Types ────────────────────────────────────────────

SUPPORTED_FILE_EXTENSIONS: Final[set[str]] = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
}

MIME_TYPE_MAP: Final[dict[str, str]] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


# ── Chunking Constants ──────────────────────────────────────────────────

CHUNKING_STRATEGIES: Final[set[str]] = {
    "fixed",
    "recursive",
    "semantic",
    "parent_child",
}

# Recursive chunking separators — ordered from most to least structural.
# The chunker tries the first separator; if chunks are still too large,
# it falls back to the next one.
RECURSIVE_SEPARATORS: Final[list[str]] = [
    "\n\n",   # Paragraph breaks (strongest structural boundary)
    "\n",     # Line breaks
    ". ",     # Sentence endings
    "? ",     # Question endings
    "! ",     # Exclamation endings
    "; ",     # Semicolon breaks
    ", ",     # Comma breaks
    " ",      # Word breaks (last resort)
]

# ── Embedding Constants ─────────────────────────────────────────────────

# Registry of supported embedding models with their metadata.
# This enables the model comparison feature and validates user choices.
EMBEDDING_MODELS: Final[dict[str, dict]] = {
    "all-MiniLM-L6-v2": {
        "dimension": 384,
        "max_tokens": 256,
        "size_mb": 80,
        "description": "Fast, lightweight. Good baseline for most use cases.",
    },
    "BAAI/bge-small-en-v1.5": {
        "dimension": 384,
        "max_tokens": 512,
        "size_mb": 130,
        "description": "Better accuracy than MiniLM. Good quality/speed tradeoff.",
    },
    "BAAI/bge-base-en-v1.5": {
        "dimension": 768,
        "max_tokens": 512,
        "size_mb": 440,
        "description": "Best quality. Use when accuracy matters more than speed.",
    },
}

# ── Retrieval Constants ─────────────────────────────────────────────────

# Reciprocal Rank Fusion smoothing constant.
# Standard value from the original RRF paper (Cormack et al., 2009).
# Higher k → more weight to lower-ranked results (smoother fusion).
RRF_K: Final[int] = 60

# Distance metric for vector search.
# Cosine similarity is the standard for sentence embeddings.
VECTOR_DISTANCE_METRIC: Final[str] = "Cosine"

# ── Generation Constants ────────────────────────────────────────────────

# Maximum context window for prompt construction (in characters).
# This is a safety limit — the actual limit depends on the LLM model.
MAX_CONTEXT_LENGTH: Final[int] = 8000

# Default system prompt for RAG generation.
DEFAULT_SYSTEM_PROMPT: Final[str] = (
    "You are a helpful, accurate, and concise assistant. "
    "Answer the user's question based ONLY on the provided context. "
    "If the context does not contain enough information to answer, "
    "say 'I don't have enough information to answer this question.' "
    "Always cite which source(s) you used."
)

# ── API Constants ───────────────────────────────────────────────────────

API_V1_PREFIX: Final[str] = "/api/v1"

# Maximum file upload size (50MB)
MAX_UPLOAD_SIZE_BYTES: Final[int] = 50 * 1024 * 1024

# ── Qdrant Constants ───────────────────────────────────────────────────

# HNSW index parameters for Qdrant.
# These control the accuracy/speed tradeoff of approximate nearest neighbor search.
# m=16, ef_construct=128 is a good balance for most use cases.
HNSW_M: Final[int] = 16
HNSW_EF_CONSTRUCT: Final[int] = 128
