"""
Embedding Model Registry — Configuration and validation for embedding models.

=== WHY THIS FILE EXISTS ===
There are hundreds of embedding models on HuggingFace. They have different:
- Dimensionalities (384, 768, 1024, etc.)
- Maximum context windows (256, 512, 8192 tokens)
- Distance metrics (Cosine, Dot Product)

If we try to store a 768-dimension vector in a 384-dimension Qdrant collection,
the database will throw an error. If we pass 1000 tokens to a model with a
256-token limit, it will silently truncate the text (ruining retrieval).

This module provides a validated registry of supported models to ensure the rest
of the system (VectorDB, Chunker) is correctly configured for the chosen model.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/embeddings/service.py
  Uses:    app/core/constants.py (EMBEDDING_MODELS)
           app/core/exceptions.py (EmbeddingModelNotFoundError)
"""

from dataclasses import dataclass
from typing import Optional

from app.core.constants import EMBEDDING_MODELS
from app.core.exceptions import EmbeddingModelNotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EmbeddingModelConfig:
    """
    Configuration for an embedding model.

    Why a dataclass instead of a dict?
    - Type safety (e.g., config.dimension is guaranteed to be an int)
    - Auto-completion in IDEs
    - Self-documenting properties

    Fields:
        name: HuggingFace model ID (e.g., 'BAAI/bge-small-en-v1.5').
        dimension: Size of the output vector (crucial for Vector DB).
        max_tokens: Maximum sequence length before truncation.
        size_mb: Approximate memory required (useful for deployment planning).
        description: Human-readable notes about when to use this model.
    """
    name: str
    dimension: int
    max_tokens: int
    size_mb: int
    description: str

    @property
    def is_compatible_with_chunk_size(self, char_chunk_size: int) -> bool:
        """
        Roughly checks if a character chunk size will fit in the token window.

        Rule of thumb in English: 1 token ≈ 4 characters.
        If chunk_size = 512 chars, that's ~128 tokens, which easily fits in a 256-token window.
        """
        approx_tokens = char_chunk_size / 4
        return approx_tokens <= self.max_tokens


def get_model_config(model_name: str) -> EmbeddingModelConfig:
    """
    Retrieve the configuration for a given model name.

    Args:
        model_name: The HuggingFace ID of the model.

    Returns:
        EmbeddingModelConfig

    Raises:
        EmbeddingModelNotFoundError: If the model is not in our registry.
    """
    if model_name not in EMBEDDING_MODELS:
        available = ", ".join(EMBEDDING_MODELS.keys())
        logger.error(f"Model '{model_name}' not found. Available: {available}")
        raise EmbeddingModelNotFoundError(
            f"Unsupported embedding model: {model_name}",
            detail=f"Please choose one of the supported models: {available}",
        )

    data = EMBEDDING_MODELS[model_name]
    return EmbeddingModelConfig(
        name=model_name,
        dimension=data["dimension"],
        max_tokens=data["max_tokens"],
        size_mb=data["size_mb"],
        description=data["description"],
    )


def list_supported_models() -> list[EmbeddingModelConfig]:
    """Return configurations for all supported models."""
    return [get_model_config(name) for name in EMBEDDING_MODELS]
