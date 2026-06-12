"""
Ingestion Endpoints — Handles file uploads and document management.

=== WHY THIS FILE EXISTS ===
Users need a way to upload PDFs and Word documents into the RAG system.
This file defines the REST API routes for uploading files, triggering the
ingestion pipeline (parsing -> chunking -> embedding -> vector DB), and
deleting documents from the database.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  Frontend Client / cURL
  Uses:    FastAPI UploadFile, app.pipeline.rag_pipeline
"""

import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks

from app.api.models import IngestionResponse, DeletionResponse, DocumentListResponse
from app.core.config import settings
from app.core.logging import get_logger

# We will build the RAG Pipeline in Phase 10 to orchestrate the actual logic
from app.pipeline.rag_pipeline import RAGPipeline, get_rag_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["Ingestion"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """
    List all uploaded documents in the knowledge base.
    """
    logger.info("Received request to list all documents")
    try:
        documents = await pipeline.list_documents()
        return DocumentListResponse(documents=documents)
    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=IngestionResponse)
async def upload_document(
    file: UploadFile = File(...),
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """
    Upload a document (PDF, DOCX, TXT, MD) to the knowledge base.
    
    The file is saved to a temporary location, processed through the ingestion
    pipeline (cleaned, chunked, embedded, and stored in Qdrant), and then
    the temporary file is deleted.
    """
    logger.info(f"Received upload request for file: {file.filename}")

    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    allowed_exts = [".pdf", ".docx", ".txt", ".md"]
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed types: {allowed_exts}"
        )

    # Fast API UploadFile objects are held in memory or as temp files.
    # We save it to disk explicitly so our PyMuPDF/Docx loaders can open it by path.
    temp_file_path = None
    try:
        # Create a temporary file that will not be automatically deleted on close
        with NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = Path(temp_file.name)

        # Pass the path to the Orchestrator Pipeline
        result = await pipeline.ingest_document(
            file_path=temp_file_path,
            original_filename=file.filename
        )

        return IngestionResponse(
            status="success",
            filename=file.filename,
            document_id=result["document_id"],
            chunks_created=result["chunks_created"],
            processing_time_sec=round(result["processing_time_sec"], 2)
        )

    except Exception as e:
        logger.error(f"Failed to process document {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Clean up: ALWAYS delete the temporary file, even if ingestion failed
        if temp_file_path and temp_file_path.exists():
            os.remove(temp_file_path)
            logger.debug(f"Cleaned up temporary file: {temp_file_path}")


@router.delete("/{document_id}", response_model=DeletionResponse)
async def delete_document(
    document_id: str,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """
    Delete a document and all its associated vector chunks from the database.
    """
    logger.info(f"Received delete request for document: {document_id}")
    
    try:
        await pipeline.delete_document(document_id)
        return DeletionResponse(
            status="success",
            document_id=document_id,
            message="Document and all associated chunks deleted."
        )
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
