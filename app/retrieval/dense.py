"""
Dense Retrieval — Vector similarity search.

=== WHY THIS FILE EXISTS ===
Dense retrieval captures the *semantic meaning* of a query.
If you search for "financial performance", dense retrieval will find chunks
about "revenue", "profits", and "EBITDA" because their embedding vectors
point in the same direction in the high-dimensional space.

This module orchestrates the dense retrieval process:
1. Receive string query
2. Convert string to vector (via EmbeddingService)
3. Search Vector DB with the vector
4. Standardize the output

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/retrieval/hybrid.py or direct API endpoints
  Uses:    app/embeddings/service.py
           app/vectordb/operations.py
           app/core/exceptions.py
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.exceptions import RetrievalError
from app.core.logging import get_logger
from app.embeddings.service import get_embedding_service
from app.vectordb.operations import search_similar
from app.retrieval.filters import DocumentFilter

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """
    Standardized output for all retrieval methods (Dense, Sparse, Hybrid).
    Decouples the rest of the application from Qdrant-specific data structures.
    """
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    source_type: str  # e.g., "dense", "sparse", "hybrid"


def retrieve_dense(
    query: str,
    top_k: int = 10,
    filters: Optional[DocumentFilter] = None
) -> List[RetrievedChunk]:
    """
    Perform a semantic vector search.

    Args:
        query: The user's search string.
        top_k: Number of results to return.
        filters: Optional metadata filters.

    Returns:
        List of RetrievedChunk objects ordered by descending semantic similarity.
    """
    if not query.strip():
        return []

    try:
        # 1. Generate the embedding for the query
        embed_service = get_embedding_service()
        query_vector = embed_service.embed_text(query)

        # 2. Prepare filters if provided
        filter_dict = filters.to_dict() if filters else None

        # 3. Search the Vector DB
        logger.debug(f"Executing dense search for: '{query}' (top_k={top_k})")
        raw_results = search_similar(
            query_vector=query_vector,
            limit=top_k,
            filters=filter_dict,
        )

        # 4. Standardize the results
        results = []
        for hit in raw_results:
            payload = hit["payload"]
            results.append(
                RetrievedChunk(
                    chunk_id=payload.get("chunk_id", "unknown"),
                    document_id=payload.get("document_id", "unknown"),
                    content=payload.get("content", ""),
                    score=hit["score"],
                    metadata={k: v for k, v in payload.items() if k not in ["content", "chunk_id", "document_id"]},
                    source_type="dense",
                )
            )

        return results

    except Exception as e:
        logger.error(f"Dense retrieval failed: {e}")
        raise RetrievalError(f"Failed to perform dense retrieval: {str(e)}") from e

