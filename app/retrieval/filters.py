"""
Metadata Filtering — Standardizes filter construction for retrieval.

=== WHY THIS FILE EXISTS ===
When a user searches "What is the Q3 revenue?", they often want to restrict
the search space to a specific document, author, or file type.
If the API layer sends raw dictionaries to the Vector DB layer, we lose
type safety and risk injection bugs.

This module defines the schema for search filters and the translation logic
to convert them into Vector DB (Qdrant) query objects.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/api/endpoints/search.py (creates DocumentFilter)
  Uses:    app/vectordb/operations.py (consumes dict format)
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentFilter(BaseModel):
    """
    Standardized schema for filtering search results.

    Why Pydantic?
    Because this will be directly used in the FastAPI endpoint as a request body.
    FastAPI will automatically validate that incoming JSON matches this schema,
    rejecting invalid fields (e.g., {"invalid_field": 123}) automatically.
    """
    file_type: Optional[str] = Field(
        default=None, 
        description="Filter by file extension (e.g., '.pdf', '.docx')"
    )
    source: Optional[str] = Field(
        default=None, 
        description="Filter by exact source filename or path"
    )
    author: Optional[str] = Field(
        default=None, 
        description="Filter by document author"
    )
    document_id: Optional[str] = Field(
        default=None,
        description="Filter to a specific document ID"
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Pydantic model to a dictionary of only the provided filters.
        This dict is passed to vectordb.operations.search_similar().
        """
        # exclude_none=True ensures we don't send {"file_type": None} to Qdrant
        return self.model_dump(exclude_none=True)
