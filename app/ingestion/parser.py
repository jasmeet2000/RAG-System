"""
Document Parser — Bridges the gap between raw loaded files and processed text.

=== WHY THIS FILE EXISTS ===
The DocumentLoader returns a RawDocument (raw text + raw metadata).
The Chunker requires clean text and standardized metadata to attach to every chunk.
The Parser sits between them. It:
1. Calls the cleaner to normalize the text
2. Normalizes format-specific metadata into a standard schema
3. Creates a ParsedDocument ready for chunking

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/ingestion/chunker.py or the main RAG pipeline
  Input:   RawDocument (from app/ingestion/loader.py)
  Output:  ParsedDocument
  Uses:    app/ingestion/cleaner.py (for text normalization)

=== WHAT HAPPENS WITHOUT IT ===
- Chunkers would have to clean text themselves (violates Single Responsibility)
- Vector DB payloads would be inconsistent. A PDF chunk might have {"pdf_title": "X"},
  while a DOCX chunk has {"docx_title": "X"}. Searching by title would require
  complex query logic to check both fields.

=== INDUSTRY ALTERNATIVES ===
- LangChain's DocumentTransformers: Similar concept, applying sequential mutations.
- ETL Pipelines (Airflow, Mage): In large systems, parsing is a distinct DAG step.

=== DESIGN DECISIONS ===
- Unified Metadata Schema: We map file-specific metadata (pdf_author, docx_author)
  into standard fields (author, title, source_type). This ensures that Vector DB
  filters can work universally across all document types.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.ingestion.loader import RawDocument
from app.ingestion.cleaner import clean_text
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ParsedDocument:
    """
    A cleaned, standardized document ready for chunking.

    Fields:
        document_id: Unique hash of the document content/source (prevents duplicates).
        content:     The cleaned, normalized text.
        source:      Original file path or URL.
        filename:    Just the filename.
        file_type:   e.g., ".pdf"
        metadata:    Standardized metadata dictionary (used as Vector DB payload).
    """
    document_id: str
    content: str
    source: str
    filename: str
    file_type: str
    metadata: dict = field(default_factory=dict)


def generate_document_id(source: str, content: str) -> str:
    """
    Generate a deterministic, unique ID for a document.

    Why deterministic?
    If we ingest the same file twice, we want the same ID so we can UPSERT
    (overwrite) in the vector DB rather than creating duplicate chunks.
    Hashing the source path + content ensures that if the file content changes,
    it gets a new ID (cache busting).
    """
    hash_input = f"{source}::{content}".encode("utf-8")
    return hashlib.sha256(hash_input).hexdigest()[:16]  # 16 chars is plenty for collision resistance


def standardize_metadata(raw_doc: RawDocument) -> dict:
    """
    Map format-specific metadata into a universal schema.

    Production Vector DBs require consistent schemas for efficient filtering.
    If we want to filter by "author", we need a single "author" key,
    not "pdf_author" and "docx_author".
    """
    raw_meta = raw_doc.metadata
    std_meta = {
        "source": raw_doc.source,
        "filename": raw_doc.filename,
        "file_type": raw_doc.file_type,
        "page_count": raw_doc.page_count,
        "loaded_at": raw_doc.loaded_at,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        # Default empty values for standardized fields
        "title": raw_doc.filename,  # Fallback
        "author": "Unknown",
        "creation_date": None,
    }

    # Format-specific mapping
    if raw_doc.file_type == ".pdf":
        if raw_meta.get("pdf_title"):
            std_meta["title"] = raw_meta["pdf_title"]
        if raw_meta.get("pdf_author"):
            std_meta["author"] = raw_meta["pdf_author"]
        std_meta["creation_date"] = raw_meta.get("pdf_created")

    elif raw_doc.file_type == ".docx":
        if raw_meta.get("docx_title"):
            std_meta["title"] = raw_meta["docx_title"]
        if raw_meta.get("docx_author"):
            std_meta["author"] = raw_meta["docx_author"]
        std_meta["creation_date"] = raw_meta.get("docx_created")

    # Remove None values to keep the Vector DB payload clean
    return {k: v for k, v in std_meta.items() if v is not None}


def parse_document(raw_doc: RawDocument, remove_citations: bool = False) -> ParsedDocument:
    """
    Parse, clean, and standardize a RawDocument.

    Args:
        raw_doc: The output from DocumentLoader.
        remove_citations: Passed to the cleaner.

    Returns:
        ParsedDocument ready for chunking.
    """
    logger.debug(f"Parsing document: {raw_doc.filename}")

    # 1. Clean the text
    cleaned_content = clean_text(raw_doc.content, remove_citations=remove_citations)

    # 2. Generate unique deterministic ID
    doc_id = generate_document_id(raw_doc.source, cleaned_content)

    # 3. Standardize metadata
    std_metadata = standardize_metadata(raw_doc)

    return ParsedDocument(
        document_id=doc_id,
        content=cleaned_content,
        source=raw_doc.source,
        filename=raw_doc.filename,
        file_type=raw_doc.file_type,
        metadata=std_metadata,
    )
