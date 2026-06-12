"""
Context Builder — Formats retrieved chunks into an LLM-digestible string.

=== WHY THIS FILE EXISTS ===
The LLM cannot read a Python `List[RetrievedChunk]` object. It only reads text.
Furthermore, if we just blindly concatenate the text of 5 chunks together, the
LLM won't know where one document ends and another begins, nor will it know
how to cite its sources.

This module converts our structured retrieval objects into a highly structured
text block with explicit source citations.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/pipeline/rag_pipeline.py
  Input:   List[RetrievedChunk]
  Output:  Tuple[str (the context block), List[dict] (citation metadata)]
"""

from typing import List, Tuple, Dict, Any
from app.retrieval.dense import RetrievedChunk
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_context(chunks: List[RetrievedChunk]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Format retrieved chunks into a single string for the LLM, and extract
    citation metadata to return to the user.

    Args:
        chunks: The top-K chunks after re-ranking.

    Returns:
        A tuple containing:
        1. The formatted context string to inject into the prompt.
        2. A list of citation dictionaries (source, filename, page, etc.).
    """
    if not chunks:
        logger.warning("Context builder received empty chunks list.")
        return "No relevant context found in the knowledge base.", []

    context_parts = []
    citations = []

    for index, chunk in enumerate(chunks, start=1):
        # Extract metadata
        meta = chunk.metadata
        filename = meta.get("filename", "Unknown Document")
        author = meta.get("author", "Unknown Author")
        
        # Build the context block for this specific chunk
        # We wrap each chunk in [Document X] tags so the LLM can reference it.
        chunk_text = (
            f"[Document {index}]\n"
            f"Source: {filename}\n"
            f"Author: {author}\n"
            f"Content:\n{chunk.content}\n"
        )
        context_parts.append(chunk_text)

        # Build the citation metadata for the API response
        # The frontend uses this to show the user exactly where the data came from.
        citations.append({
            "id": index,
            "document_id": chunk.document_id,
            "filename": filename,
            "source": meta.get("source", "Unknown"),
            "score": chunk.score,  # Useful for debugging
        })

    # Join with clear separators
    full_context_string = "\n---\n\n".join(context_parts)
    
    return full_context_string, citations
