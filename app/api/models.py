"""
API Pydantic Models — Request and Response schemas.

=== WHY THIS FILE EXISTS ===
FastAPI uses Pydantic to automatically:
1. Validate incoming JSON payloads.
2. Generate interactive OpenAPI (Swagger) documentation.
3. Serialize Python objects into outgoing JSON.

By defining explicit schemas here, we guarantee that the frontend client
and the backend server agree on the data contract.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  Frontend client, app/api/endpoints/search.py
  Uses:    app/retrieval/filters.py (DocumentFilter)
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.retrieval.filters import DocumentFilter


# ── Ingestion Models ─────────────────────────────────────────────────────────

class IngestionResponse(BaseModel):
    """Response returned after successfully uploading and processing a document."""
    status: str = Field(..., description="E.g., 'success' or 'error'")
    filename: str = Field(..., description="Name of the uploaded file")
    document_id: str = Field(..., description="Deterministic ID of the ingested document")
    chunks_created: int = Field(..., description="How many vector chunks were created")
    processing_time_sec: float = Field(..., description="Time taken to parse, chunk, and embed")


class DeletionResponse(BaseModel):
    """Response returned after deleting a document."""
    status: str
    document_id: str
    message: str


class DocumentItem(BaseModel):
    """Represents a single document in the knowledge base."""
    document_id: str = Field(..., description="The ID of the document")
    filename: str = Field(..., description="The name of the file")
    uploaded_at: Optional[str] = Field(default=None, description="ISO timestamp of when the document was parsed")


class DocumentListResponse(BaseModel):
    """Response returned when fetching the list of all documents."""
    documents: List[DocumentItem] = Field(..., description="List of unique documents")



# ── Search Models ────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    """
    The incoming payload when a user asks a question.
    """
    query: str = Field(..., description="The user's question", min_length=1)
    
    # Advanced Options
    top_k: int = Field(default=5, description="Number of final documents to use as context", ge=1, le=20)
    filters: Optional[DocumentFilter] = Field(default=None, description="Metadata filters to apply to the vector search")
    stream: bool = Field(default=True, description="Whether to stream the LLM response via Server-Sent Events (SSE)")
    hybrid_search: bool = Field(default=True, description="If True, uses RRF (Dense + Sparse). If False, uses Dense only.")


class SearchCitation(BaseModel):
    """A single citation block to tell the frontend where data came from."""
    id: int
    document_id: str
    filename: str
    title: str = Field(default="Untitled", description="Human-readable document title")
    source: str
    score: float = Field(..., description="Normalized relevance score between 0.0 and 1.0")
    text: str = Field(default="", description="Snippet preview of the chunk content (up to 300 chars)")
    chunk_index: int = Field(default=0, description="Position of this chunk within the document")
    page: Optional[int] = Field(default=None, description="Page number if available (PDFs)")
    retrieval_method: str = Field(default="Semantic", description="How this chunk was retrieved")


class SearchResponse(BaseModel):
    """
    The complete response for non-streaming requests.
    """
    answer: str = Field(..., description="The complete LLM response")
    citations: List[SearchCitation] = Field(..., description="Sources used to generate the answer")
    processing_time_sec: float = Field(..., description="Total time taken for retrieval + generation")


# ── Streaming Models ─────────────────────────────────────────────────────────
# For Server-Sent Events (SSE), we don't return a single JSON object.
# We yield chunks formatted like: `data: {"event": "token", "text": "Hello"}\n\n`

class StreamEvent(BaseModel):
    """
    A single event in the Server-Sent Events (SSE) stream.
    """
    event: str = Field(..., description="Event type: 'token', 'citations', 'error', 'done'")
    data: Any = Field(..., description="Payload (string for 'token', list of dicts for 'citations')")
