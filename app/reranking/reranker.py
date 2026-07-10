"""
Cross-Encoder Re-ranking Service.

=== WHY THIS FILE EXISTS ===
In Phase 4, we used Bi-Encoders to generate embeddings. Bi-encoders process the
query and the document completely separately. This makes search incredibly fast
(we can pre-compute millions of document vectors), but it loses fine-grained 
semantic interactions between the query and the document text.

A Cross-Encoder processes the query and the document *together* through all
layers of the Transformer model. The attention mechanism can directly compare
words in the query to words in the document.

Result: Cross-Encoders are ~100x more accurate but ~1000x slower than Bi-Encoders.

=== THE TWO-STAGE RETRIEVAL PATTERN ===
Because Cross-Encoders are too slow to run against an entire database, we use
the industry-standard two-stage retrieval pattern:
1. Stage 1 (Retrieval): Use Bi-Encoders + BM25 to quickly retrieve Top-20 candidates.
2. Stage 2 (Re-ranking): Use a Cross-Encoder to re-score only those 20 candidates
   and return the Top-5 absolute best matches to the LLM.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/pipeline/rag_pipeline.py
  Input:   Query (str) + List of RetrievedChunk (from Phase 6)
  Output:  Sorted, filtered List of RetrievedChunk
"""

import math
import time
from typing import List, Optional

from app.core.config import settings
from app.core.exceptions import RerankingError
from app.core.logging import get_logger
from app.retrieval.dense import RetrievedChunk

logger = get_logger(__name__)

# Singleton instance
_reranker_service: Optional["RerankerService"] = None


class RerankerService:
    """
    Service for re-scoring retrieval candidates using a Cross-Encoder model.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """
        Load the CrossEncoder model into memory.
        Like the EmbeddingService, this is an expensive operation that should
        only happen once at startup.
        """
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise RerankingError(
                "sentence-transformers is not installed.",
                detail=str(e),
            ) from e

        logger.info(f"Loading CrossEncoder re-ranker model '{self.model_name}'...")
        start_time = time.perf_counter()

        try:
            # We load the model. sentence-transformers auto-detects GPU/CPU.
            self.model = CrossEncoder(self.model_name)
        except Exception as e:
            raise RerankingError(
                f"Failed to load re-ranker model '{self.model_name}'",
                detail=str(e),
            ) from e

        elapsed = time.perf_counter() - start_time
        logger.info(f"Re-ranker model loaded successfully in {elapsed:.2f}s")

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """
        Re-score and re-order a list of candidate chunks against the query.

        Args:
            query: The original user search query.
            candidates: The list of chunks returned by dense/sparse/hybrid retrieval.
            top_k: Number of final results to keep.

        Returns:
            A new list of RetrievedChunk objects, sorted by CrossEncoder score.
        """
        if not candidates:
            return []

        if self.model is None:
            raise RerankingError("Re-ranker model is not loaded.")

        start_time = time.perf_counter()

        # The CrossEncoder expects a list of pairs: [[query, text1], [query, text2], ...]
        sentence_combinations = [[query, chunk.content] for chunk in candidates]

        try:
            # Predict scores for all pairs in a single batch operation
            # Scores are unnormalized logits (can be negative or positive)
            scores = self.model.predict(sentence_combinations)
        except Exception as e:
            raise RerankingError(
                f"Failed to compute re-ranking scores for {len(candidates)} candidates.",
                detail=str(e),
            ) from e

        # Normalize raw logits to [0, 1] via sigmoid so the frontend
        # can display them as meaningful 0-100% relevance scores.
        for chunk, score in zip(candidates, scores):
            chunk.score = 1.0 / (1.0 + math.exp(-float(score)))

        # Sort descending by the new CrossEncoder score
        candidates.sort(key=lambda x: x.score, reverse=True)

        elapsed = time.perf_counter() - start_time
        logger.debug(
            f"Re-ranked {len(candidates)} candidates in {elapsed:.3f}s. "
            f"Keeping top {top_k}."
        )

        return candidates[:top_k]


def get_reranker_service() -> RerankerService:
    """
    Get the singleton instance of the RerankerService.
    Initializes the model on the first call.
    """
    global _reranker_service

    if _reranker_service is None:
        _reranker_service = RerankerService(model_name=settings.RERANKER_MODEL)

    return _reranker_service
