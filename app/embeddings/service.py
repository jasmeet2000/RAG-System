"""
Embedding Service — Generates vector embeddings for text chunks.

=== WHY THIS FILE EXISTS ===
Embedding models (like SentenceTransformers) are large neural networks (80MB to 1GB+).
Loading them into RAM/VRAM takes several seconds.

If we loaded the model every time we processed a chunk or a user query:
- Document ingestion would be 100x slower.
- User queries would take 3-5 seconds just to load the model.

This module implements the SINGLETON PATTERN to ensure the model is loaded
exactly once at application startup and kept in memory for the lifetime of the app.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/pipeline/rag_pipeline.py, app/api/endpoints/search.py
  Input:   List of strings (chunk contents or user queries)
  Output:  List of vectors (List[List[float]])
  Uses:    sentence-transformers, app/embeddings/models.py

=== WHAT HAPPENS WITHOUT IT ===
- Out of Memory (OOM) errors from loading the model multiple times.
- Extremely slow response times due to constant disk I/O.

=== INDUSTRY BEST PRACTICES USED HERE ===
1. Batch Processing: Neural networks are highly optimized for matrix math.
   Embedding 32 chunks at once is almost exactly as fast as embedding 1 chunk.
   We expose `embed_batch()` to take advantage of this.
2. Lazy Initialization: The model isn't loaded when the module is imported,
   only when it is first used (or explicitly initialized during FastAPI startup).
3. Normalization: We normalize vectors to length 1.0 so we can use Dot Product
   search in the Vector DB (which is faster than Cosine Similarity calculation).
"""

import time
from typing import List, Optional

from app.core.config import settings
from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger
from app.embeddings.models import EmbeddingModelConfig, get_model_config

logger = get_logger(__name__)

# The singleton instance
_embedding_service: Optional["EmbeddingService"] = None


class EmbeddingService:
    """
    Service for generating text embeddings using SentenceTransformers.
    """

    def __init__(self, model_name: str):
        """
        Initialize the embedding service.
        Do not call this directly; use get_embedding_service() instead.
        """
        self.config: EmbeddingModelConfig = get_model_config(model_name)
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the model into memory. This is the expensive operation."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise EmbeddingError(
                "sentence-transformers is not installed. Run: pip install sentence-transformers",
                detail=str(e),
            ) from e

        logger.info(
            f"Loading embedding model '{self.config.name}' "
            f"({self.config.size_mb} MB, {self.config.dimension} dims)..."
        )
        
        start_time = time.perf_counter()
        
        try:
            # We don't specify device="cuda" explicitly. SentenceTransformers
            # automatically detects and uses a GPU if available.
            self.model = SentenceTransformer(self.config.name)
            
            # Ensure the model truncates sequences that exceed its max_tokens
            # rather than throwing an error.
            self.model.max_seq_length = self.config.max_tokens
            
        except Exception as e:
            raise EmbeddingError(
                f"Failed to load embedding model '{self.config.name}'",
                detail=str(e),
            ) from e

        elapsed = time.perf_counter() - start_time
        logger.info(
            f"Embedding model loaded successfully in {elapsed:.2f}s "
            f"(Device: {self.model.device})"
        )

    def embed_text(self, text: str) -> List[float]:
        """
        Generate an embedding for a single string.
        Typically used for user queries.
        """
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """
        Generate embeddings for a list of strings.
        Typically used during document ingestion.

        Args:
            texts: List of text chunks to embed.
            batch_size: Override the default batch size if needed.

        Returns:
            List of embedding vectors (List of floats).
            
        Why normalize_embeddings=True?
        Normalizing vectors to unit length (L2 norm = 1) allows Vector DBs
        to compute Cosine Similarity using the Dot Product metric, which is
        significantly faster mathematically.
        """
        if not texts:
            return []

        if self.model is None:
            raise EmbeddingError("Embedding model is not loaded.")

        bs = batch_size or settings.EMBEDDING_BATCH_SIZE
        start_time = time.perf_counter()

        try:
            # The model.encode() method returns a numpy array.
            # We convert it to a python list of lists (float) because Vector DB
            # clients (like Qdrant) require native python types for JSON serialization.
            embeddings_array = self.model.encode(
                texts,
                batch_size=bs,
                normalize_embeddings=True,  # Crucial for fast vector search
                show_progress_bar=False,
            )
            
            embeddings: List[List[float]] = embeddings_array.tolist()

        except Exception as e:
            raise EmbeddingError(
                f"Failed to generate embeddings for batch of {len(texts)} items.",
                detail=str(e),
            ) from e

        elapsed = time.perf_counter() - start_time
        logger.debug(
            f"Embedded {len(texts)} items in {elapsed:.3f}s "
            f"({len(texts)/elapsed:.1f} items/sec)"
        )

        return embeddings


def get_embedding_service() -> EmbeddingService:
    """
    Get the singleton instance of the EmbeddingService.

    This implements the Singleton pattern. The first time this is called,
    it initializes the model (takes a few seconds). Subsequent calls return
    the already-loaded instance immediately.

    In FastAPI, this is typically called during the lifespan startup event
    to ensure the model is ready before accepting requests.
    """
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL_NAME)
        
    return _embedding_service


def reset_embedding_service() -> None:
    """
    Force reload the embedding service.
    Useful for testing or if the model crashes (rare).
    """
    global _embedding_service
    _embedding_service = None
