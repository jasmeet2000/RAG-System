"""
Vector Database Operations — CRUD and Search.

=== WHY THIS FILE EXISTS ===
This module abstracts the Qdrant-specific API from our business logic.
It translates our internal `DocumentChunk` models into Qdrant `PointStruct`s,
handles batch upserts, and provides search functionality.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/pipeline/rag_pipeline.py
  Uses:    app/vectordb/client.py, app/core/exceptions.py

=== WHAT HAPPENS WITHOUT IT ===
Our RAG pipeline would be tightly coupled to Qdrant's specific syntax.
If we ever wanted to swap to Pinecone or Weaviate, we'd have to rewrite
the entire ingestion and retrieval pipeline.

=== INDUSTRY BEST PRACTICES ===
- Upsert over Insert: Using deterministic UUIDs allows us to re-ingest a document
  and overwrite the old chunks instead of creating duplicates.
- Payload Management: We store the actual text chunk inside the Vector DB payload.
  This allows us to retrieve the text directly during search, rather than doing
  a secondary lookup in a relational database.
"""

import uuid
from typing import List, Dict, Any, Optional

from qdrant_client.http import models

from app.core.config import settings
from app.core.exceptions import VectorDBError
from app.core.logging import get_logger
from app.ingestion.chunker import DocumentChunk
from app.vectordb.client import get_qdrant_client

logger = get_logger(__name__)


def _generate_uuid_from_string(val: str) -> str:
    """
    Qdrant requires point IDs to be either integers or valid UUIDs.
    Our chunk_id from Phase 3 is a string like 'hash_chunk_0'.
    We use uuid.uuid5 to deterministically convert our string ID into a UUID.
    """
    NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid.uuid5(NAMESPACE, val))


def upsert_chunks(chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
    """
    Insert or update a batch of document chunks into Qdrant.

    Args:
        chunks: List of DocumentChunk objects from the Chunker.
        embeddings: List of embedding vectors from the EmbeddingService.
                    Must be exactly the same length as `chunks`.

    Raises:
        VectorDBError: If lengths mismatch or insertion fails.
    """
    if not chunks:
        return

    if len(chunks) != len(embeddings):
        raise VectorDBError(
            f"Length mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings."
        )

    client = get_qdrant_client()
    collection_name = settings.QDRANT_COLLECTION_NAME

    # Convert our internal models to Qdrant PointStructs
    points = []
    for chunk, vector in zip(chunks, embeddings):
        point_id = _generate_uuid_from_string(chunk.chunk_id)
        
        # The payload is what we get back when we search.
        # It must contain the actual text, plus all metadata.
        payload = {
            "content": chunk.content,
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
        }
        # Merge in the document metadata (author, source, etc.)
        payload.update(chunk.metadata)

        points.append(
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        )

    try:
        # We use a batch size of 100 to prevent timeout/memory issues
        # on very large documents.
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            client.upsert(
                collection_name=collection_name,
                points=batch,
            )
        
        logger.info(f"Successfully upserted {len(points)} chunks to Qdrant.")
    except Exception as e:
        raise VectorDBError(f"Failed to upsert chunks: {str(e)}") from e


def search_similar(
    query_vector: List[float],
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[dict]:
    """
    Perform a dense vector similarity search.

    Args:
        query_vector: The embedded user query.
        limit: Number of results to return (top_k).
        filters: Optional dictionary of metadata filters (e.g., {"file_type": ".pdf"}).

    Returns:
        List of dictionaries containing the payload and similarity score.
    """
    client = get_qdrant_client()
    
    # Build Qdrant Filter objects if metadata filters are provided
    query_filter = None
    if filters:
        must_conditions = []
        for key, value in filters.items():
            must_conditions.append(
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value)
                )
            )
        query_filter = models.Filter(must=must_conditions)

    try:
        search_response = client.query_points(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,  # Crucial: return the actual text and metadata
            with_vectors=False, # We don't need the vector back, saves bandwidth
        )
        
        # Format the output to decouple from Qdrant-specific objects
        results = []
        for hit in search_response.points:
            results.append({
                "score": hit.score,
                "payload": hit.payload,
            })
            
        return results

    except Exception as e:
        raise VectorDBError(f"Vector search failed: {str(e)}") from e


def delete_document(document_id: str) -> None:
    """
    Delete all chunks associated with a specific document ID.
    
    This shows the power of payload indexing. We can tell Qdrant:
    "Delete all vectors where payload.document_id == X".
    """
    client = get_qdrant_client()
    
    try:
        client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id)
                        )
                    ]
                )
            ),
        )
        logger.info(f"Deleted all chunks for document {document_id}")
    except Exception as e:
        raise VectorDBError(f"Failed to delete document: {str(e)}") from e


def list_documents() -> List[Dict[str, str]]:
    """
    Retrieve a unique list of all ingested documents.
    We do this by scrolling through the points and deduplicating by document_id.
    """
    client = get_qdrant_client()
    
    try:
        documents = {}
        offset = None
        
        while True:
            records, next_offset = client.scroll(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                limit=1000,
                with_payload=["document_id", "filename", "parsed_at"],
                with_vectors=False,
                offset=offset,
            )
            
            for record in records:
                if record.payload:
                    doc_id = record.payload.get("document_id")
                    filename = record.payload.get("filename", "Unknown")
                    parsed_at = record.payload.get("parsed_at")
                    if doc_id and doc_id not in documents:
                        documents[doc_id] = {
                            "document_id": doc_id,
                            "filename": filename,
                            "uploaded_at": parsed_at
                        }
            
            if next_offset is None:
                break
            offset = next_offset
            
        # Sort documents by uploaded_at descending
        doc_list = list(documents.values())
        doc_list.sort(key=lambda x: x.get("uploaded_at") or "", reverse=True)
        return doc_list

    except Exception as e:
        raise VectorDBError(f"Failed to list documents: {str(e)}") from e
