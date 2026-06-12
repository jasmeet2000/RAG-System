"""
Hybrid Retrieval — Combining Dense and Sparse Search via RRF.

=== WHY THIS FILE EXISTS ===
Dense retrieval finds conceptual matches ("finance" -> "money").
Sparse retrieval finds exact keyword matches ("Tesla Model S").
Neither is perfect on its own. Hybrid search gives you the best of both.

But how do you combine the lists?
Dense scores are Cosine Similarity (0.0 to 1.0).
Sparse scores are BM25 (0.0 to theoretically infinity).
You cannot simply add `dense_score + sparse_score` — they are on different scales!

=== INDUSTRY SOLUTION: Reciprocal Rank Fusion (RRF) ===
Instead of combining the *scores*, RRF combines the *ranks* (positions) of the
documents in each list. 

The formula: RRF_Score = 1 / (k + Rank)
Where `k` is a smoothing constant (traditionally 60).

Example:
Chunk A is Rank 1 in Dense, Rank 5 in Sparse.
Score = (1 / (60 + 1)) + (1 / (60 + 5)) = 0.0163 + 0.0153 = 0.0316

This module executes both searches in parallel (using async or threads)
and merges the results perfectly.
"""

import asyncio
from typing import List, Dict, Optional

from app.core.config import settings
from app.core.constants import RRF_K
from app.core.logging import get_logger
from app.retrieval.dense import retrieve_dense, RetrievedChunk
from app.retrieval.sparse import retrieve_sparse
from app.retrieval.filters import DocumentFilter

logger = get_logger(__name__)


def compute_rrf(
    dense_results: List[RetrievedChunk],
    sparse_results: List[RetrievedChunk],
    top_k: int = 10,
) -> List[RetrievedChunk]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.
    
    Args:
        dense_results: Sorted list from dense retrieval.
        sparse_results: Sorted list from sparse retrieval.
        top_k: Number of final results to return.
        
    Returns:
        Merged and re-ranked list of RetrievedChunk objects.
    """
    # Dictionary to accumulate RRF scores by chunk_id
    # Format: {chunk_id: {"score": float, "chunk": RetrievedChunk}}
    merged: Dict[str, dict] = {}

    # Helper function to process a list and assign RRF scores
    def process_list(results: List[RetrievedChunk], source_label: str):
        for rank, chunk in enumerate(results, start=1):
            rrf_score = 1.0 / (RRF_K + rank)
            
            if chunk.chunk_id not in merged:
                # Update the source_type to indicate it was part of a hybrid search
                # We clone the chunk to avoid mutating the original
                hybrid_chunk = RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    score=0.0,  # Will hold the RRF score
                    metadata=chunk.metadata,
                    source_type=source_label,
                )
                merged[chunk.chunk_id] = {"score": rrf_score, "chunk": hybrid_chunk}
            else:
                # Document was found by BOTH retrievers
                merged[chunk.chunk_id]["score"] += rrf_score
                # Update source to indicate BOTH found it
                merged[chunk.chunk_id]["chunk"].source_type = "hybrid_both"

    # Process both lists
    process_list(dense_results, "hybrid_dense")
    process_list(sparse_results, "hybrid_sparse")

    # Re-assign the RRF score back into the chunk object
    final_results = []
    for data in merged.values():
        chunk = data["chunk"]
        chunk.score = data["score"]
        final_results.append(chunk)

    # Sort by the new RRF score descending
    final_results.sort(key=lambda x: x.score, reverse=True)
    
    return final_results[:top_k]


async def retrieve_hybrid(
    query: str,
    top_k: int = 10,
    filters: Optional[DocumentFilter] = None
) -> List[RetrievedChunk]:
    """
    Perform hybrid retrieval (Dense + Sparse + RRF).
    
    This function runs both dense and sparse retrieval concurrently
    to minimize latency.
    """
    logger.info(f"Executing Hybrid Retrieval for: '{query}'")

    # In a real async application, we'd use asyncio.gather to run these in parallel.
    # Since our dense and sparse functions are currently synchronous (using Qdrant
    # synchronous client and CPU-bound rank_bm25), we run them sequentially here,
    # or use asyncio.to_thread to prevent blocking the event loop.

    dense_task = asyncio.to_thread(
        retrieve_dense, query, top_k=top_k * 2, filters=filters
    )
    sparse_task = asyncio.to_thread(
        retrieve_sparse, query, top_k=top_k * 2, filters=filters
    )

    # Note: We request top_k * 2 from the base retrievers to ensure we have
    # enough overlap for the RRF algorithm to perform effectively.
    
    dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)
    
    logger.debug(
        f"Retrieved {len(dense_results)} dense and {len(sparse_results)} sparse candidates"
    )

    # Merge using RRF
    final_results = compute_rrf(dense_results, sparse_results, top_k=top_k)
    
    logger.info(f"Hybrid retrieval complete. Yielded {len(final_results)} top results.")
    return final_results
