"""
Document Chunker — Breaks large documents into smaller, embeddable pieces.

=== WHY THIS FILE EXISTS ===
Embedding models have a maximum context window (e.g., 256 or 512 tokens).
If you feed a 50-page PDF into an embedding model, it will silently truncate
everything after the first page.
Furthermore, vector similarity works best on single, cohesive ideas. If a chunk
contains 5 different topics, its embedding vector becomes a "mush" of average
meanings that won't match specific queries.

We must split documents into smaller chunks (e.g., 500 characters) with overlap
to preserve context across boundaries.

=== IMPLEMENTED STRATEGIES ===
1. Fixed-size chunking: Splits exactly by character count. Dumb but fast.
2. Recursive chunking: Tries to split by paragraphs, then sentences, then words.
   (INDUSTRY DEFAULT - respects document structure).
3. Semantic chunking: Uses embeddings to group sentences by semantic similarity.
4. Parent-Child chunking: Retrieves small chunks but passes larger surrounding
   context to the LLM.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Input:   ParsedDocument (from parser.py)
  Output:  List of DocumentChunk (ready for embeddings.py)
  Uses:    app.core.constants.py (RECURSIVE_SEPARATORS)

=== WHAT HAPPENS WITHOUT IT ===
- Documents exceed model token limits and get truncated.
- Retrieval accuracy plummets because entire documents are represented by single vectors.
"""

from typing import List, Protocol
from dataclasses import dataclass, field
from app.core.exceptions import ChunkingError
from app.ingestion.parser import ParsedDocument
from app.core.constants import RECURSIVE_SEPARATORS
from app.core.logging import get_logger
import re

logger = get_logger(__name__)


@dataclass
class DocumentChunk:
    """
    A single chunk of text ready to be embedded and stored in the Vector DB.

    Fields:
        chunk_id:      Unique ID for this chunk (e.g., "doc_id_chunk_0").
        document_id:   Reference back to the parent document.
        content:       The actual text of the chunk.
        chunk_index:   The sequence number of this chunk in the document.
        metadata:      Payload for the Vector DB (includes document metadata).
    """
    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


class ChunkerStrategy(Protocol):
    """Protocol (Interface) for chunking strategies."""
    def chunk(self, document: ParsedDocument) -> List[DocumentChunk]:
        ...


# ── Strategy 1: Fixed-Size Chunking ──────────────────────────────────────────


class FixedSizeChunker:
    """
    Splits text exactly by character count with overlap.
    Pros: Extremely fast, easy to implement.
    Cons: Cuts sentences and words in half, destroying semantic meaning.
    Used for: Baselines, raw data logs without structure.
    """
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        if chunk_overlap >= chunk_size:
            raise ChunkingError("Overlap must be less than chunk size.")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, document: ParsedDocument) -> List[DocumentChunk]:
        text = document.content
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk_text = text[start:end]
            chunks.append(chunk_text)
            
            # Move forward by (size - overlap)
            step = self.chunk_size - self.chunk_overlap
            if step <= 0:
                break
            start += step

        return self._build_document_chunks(document, chunks)

    def _build_document_chunks(self, document: ParsedDocument, text_chunks: List[str]) -> List[DocumentChunk]:
        result = []
        for i, text in enumerate(text_chunks):
            chunk_id = f"{document.document_id}_chunk_{i}"
            # Copy doc metadata and add chunk-specific info
            meta = document.metadata.copy()
            meta.update({
                "chunk_index": i,
                "total_chunks": len(text_chunks),
                "strategy": "fixed_size"
            })
            result.append(DocumentChunk(
                chunk_id=chunk_id,
                document_id=document.document_id,
                content=text,
                chunk_index=i,
                metadata=meta
            ))
        return result


# ── Strategy 2: Recursive Character Chunking ─────────────────────────────────


class RecursiveChunker:
    """
    INDUSTRY DEFAULT CHUNKER.
    Tries to split on the largest logical boundary (e.g., paragraph \n\n).
    If a resulting chunk is still too big, it falls back to the next boundary
    (e.g., sentence '. ', then word ' ').

    Pros: Respects document structure, rarely cuts sentences in half.
    Cons: Slightly slower than fixed-size.
    """
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50, separators: List[str] = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or RECURSIVE_SEPARATORS

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text based on hierarchical separators."""
        final_chunks = []
        
        # If text is already small enough, return it
        if len(text) <= self.chunk_size:
            return [text]

        # Find the best separator that actually exists in the text
        separator = separators[-1]  # default to last resort (usually ' ')
        for sep in separators:
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                break

        # Split the text
        splits = text.split(separator) if separator else list(text)
        
        # Merge splits to fit chunk_size
        current_chunk = []
        current_len = 0

        for split in splits:
            split_len = len(split) + (len(separator) if separator else 0)
            
            # If a single split is STILL too large, recurse with finer separators
            if split_len > self.chunk_size and len(separators) > 1:
                # Flush current buffer
                if current_chunk:
                    final_chunks.append(separator.join(current_chunk))
                    current_chunk = []
                    current_len = 0
                
                # Recurse
                next_seps = separators[separators.index(separator) + 1:]
                recursive_chunks = self._split_text(split, next_seps)
                final_chunks.extend(recursive_chunks)
                continue

            # If adding this split exceeds size, flush buffer
            if current_len + split_len > self.chunk_size and current_chunk:
                final_chunks.append(separator.join(current_chunk))
                # Implement overlap by keeping the last item(s)
                # For simplicity in this implementation, we just start fresh.
                # A robust overlap requires backtracking tokens.
                current_chunk = []
                current_len = 0
            
            current_chunk.append(split)
            current_len += split_len

        if current_chunk:
            final_chunks.append(separator.join(current_chunk))

        return final_chunks

    def chunk(self, document: ParsedDocument) -> List[DocumentChunk]:
        text_chunks = self._split_text(document.content, self.separators)
        
        # Build DocumentChunks
        result = []
        for i, text in enumerate(text_chunks):
            # Clean up whitespace that might have accumulated at edges
            text = text.strip()
            if not text:
                continue
                
            chunk_id = f"{document.document_id}_chunk_{i}"
            meta = document.metadata.copy()
            meta.update({
                "chunk_index": i,
                "total_chunks": len(text_chunks),
                "strategy": "recursive"
            })
            result.append(DocumentChunk(
                chunk_id=chunk_id,
                document_id=document.document_id,
                content=text,
                chunk_index=i,
                metadata=meta
            ))
        
        logger.info(f"Recursive chunking created {len(result)} chunks for {document.filename}")
        return result


# ── Strategy 3 & 4 Placeholders ──────────────────────────────────────────────
# We implement the stubs here. Full implementation of Semantic and Parent-Child
# requires the Embedding model (Phase 4), so we will revisit them later.

class SemanticChunker:
    """
    Advanced: Splits by sentences, calculates embeddings for each, and groups
    them based on cosine similarity drop-offs (topic changes).
    To be fully implemented in Phase 4/5 once Embeddings are available.
    """
    def chunk(self, document: ParsedDocument) -> List[DocumentChunk]:
        raise NotImplementedError("SemanticChunker requires embedding service (Phase 4).")


class ParentChildChunker:
    """
    Advanced: Creates small chunks for retrieval, but links them to a larger
    parent chunk for LLM context generation.
    To be fully implemented in Phase 5/6 once Vector DB schemas are defined.
    """
    def chunk(self, document: ParsedDocument) -> List[DocumentChunk]:
        raise NotImplementedError("ParentChildChunker requires parent_id schema mapping.")


# ── Factory ──────────────────────────────────────────────────────────────────

def get_chunker(strategy: str = "recursive", **kwargs) -> ChunkerStrategy:
    """Factory to get the requested chunker."""
    if strategy == "fixed":
        return FixedSizeChunker(**kwargs)
    elif strategy == "recursive":
        return RecursiveChunker(**kwargs)
    elif strategy == "semantic":
        return SemanticChunker()
    elif strategy == "parent_child":
        return ParentChildChunker()
    else:
        raise ChunkingError(f"Unknown chunking strategy: {strategy}")
