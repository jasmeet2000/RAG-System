"""
RAG Pipeline Orchestrator — The "Brain" of the application.

=== WHY THIS FILE EXISTS ===
Up until now, we have built highly specialized, isolated modules.
The loader only loads. The vector DB only searches. The LLM only generates.
None of them know about each other.

The Orchestrator ties everything together into two main workflows:
1. Ingestion Workflow: File -> Loader -> Cleaner -> Chunker -> Embedder -> Vector DB.
2. Retrieval Workflow: Query -> Retriever -> Reranker -> Context Builder -> LLM -> User.

By keeping this logic in an Orchestrator class, our API endpoints (`app/api/endpoints/`)
remain extremely thin and clean, completely decoupled from the underlying logic.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/api/endpoints/search.py, app/api/endpoints/ingestion.py
  Uses:    Virtually every other module we've built in Phases 3-8.
"""

import time
from pathlib import Path
from typing import Dict, Any, Tuple, AsyncGenerator, Optional, List

from app.api.models import StreamEvent
from app.core.config import settings
from app.core.exceptions import RAGPipelineError
from app.core.logging import get_logger

# Ingestion
from app.ingestion.loader import load_document
from app.ingestion.parser import parse_document
from app.ingestion.chunker import get_chunker

# Embeddings & Vector DB
from app.embeddings.service import get_embedding_service
from app.vectordb.operations import upsert_chunks, delete_document as vdb_delete_document, list_documents as vdb_list_documents

# Retrieval & Re-ranking
from app.retrieval.dense import retrieve_dense
from app.retrieval.hybrid import retrieve_hybrid
from app.retrieval.sparse import rebuild_bm25_index
from app.retrieval.filters import DocumentFilter
from app.reranking.reranker import get_reranker_service

# Generation
from app.generation.context import build_context
from app.generation.prompts import RAG_SYSTEM_PROMPT, RAG_USER_PROMPT_TEMPLATE
from app.generation.llm import get_llm_service

logger = get_logger(__name__)

# Singleton instance for FastAPI Dependency Injection
_rag_pipeline: Optional["RAGPipeline"] = None


class RAGPipeline:
    """
    Orchestrates the end-to-end Retrieval-Augmented Generation workflows.
    """

    async def ingest_document(self, file_path: Path, original_filename: str) -> Dict[str, Any]:
        """
        End-to-end ingestion workflow.
        """
        logger.info(f"Pipeline started: Ingesting '{original_filename}'")
        start_time = time.perf_counter()

        try:
            # 1. Load (Extract raw text)
            raw_doc = load_document(file_path)
            # Override filename since the loader might see a temp file name
            raw_doc.filename = original_filename

            # 2. Parse & Clean (Normalize text, standardize metadata)
            parsed_doc = parse_document(raw_doc)

            # 3. Chunk (Split into 512-character overlapping chunks)
            chunker = get_chunker("recursive", chunk_size=512, chunk_overlap=50)
            chunks = chunker.chunk(parsed_doc)

            if not chunks:
                raise RAGPipelineError("Document resulted in 0 chunks after parsing.")

            # 4. Embed (Convert text chunks to vectors)
            embed_service = get_embedding_service()
            chunk_texts = [c.content for c in chunks]
            embeddings = embed_service.embed_batch(chunk_texts)

            # 5. Store (Upsert to Qdrant)
            upsert_chunks(chunks, embeddings)

            # 6. Rebuild Sparse Index
            # Since we use an in-memory BM25 index for this project, we must
            # rebuild it so the new document is searchable via exact keywords.
            rebuild_bm25_index()

            elapsed = time.perf_counter() - start_time
            logger.info(f"Pipeline finished: Ingested {len(chunks)} chunks in {elapsed:.2f}s")

            return {
                "document_id": parsed_doc.document_id,
                "chunks_created": len(chunks),
                "processing_time_sec": elapsed,
            }

        except Exception as e:
            logger.error(f"Ingestion pipeline failed: {e}")
            raise RAGPipelineError(f"Ingestion failed: {str(e)}") from e

    async def answer_question(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[DocumentFilter] = None,
        use_hybrid: bool = True
    ) -> Tuple[str, list]:
        """
        End-to-end retrieval and generation workflow (Blocking).
        """
        logger.info(f"Pipeline started: Answering query '{query}'")

        try:
            # 1. Retrieval (Stage 1 of Two-Stage Retrieval)
            # We fetch more candidates than we need (e.g., 20) for the re-ranker
            fetch_k = max(20, top_k * 3)
            
            if use_hybrid:
                candidates = await retrieve_hybrid(query, top_k=fetch_k, filters=filters)
            else:
                candidates = retrieve_dense(query, top_k=fetch_k, filters=filters)

            # 2. Re-ranking (Stage 2 of Two-Stage Retrieval)
            reranker = get_reranker_service()
            top_chunks = reranker.rerank(query, candidates, top_k=top_k)

            # 3. Context Building (Format for the LLM)
            context_str, citations = build_context(top_chunks)

            # 4. Prompt Formatting
            user_prompt = RAG_USER_PROMPT_TEMPLATE.substitute(
                context_str=context_str,
                query=query
            )

            # 5. LLM Generation
            llm_service = get_llm_service()
            answer = await llm_service.generate(
                system_prompt=RAG_SYSTEM_PROMPT,
                user_prompt=user_prompt
            )

            return answer, citations

        except Exception as e:
            logger.error(f"Answer pipeline failed: {e}")
            raise RAGPipelineError(f"Failed to answer question: {str(e)}") from e

    async def answer_question_stream(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[DocumentFilter] = None,
        use_hybrid: bool = True
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        End-to-end retrieval and generation workflow (Streaming).
        Yields Pydantic StreamEvent objects for the API to format as SSE.
        """
        logger.info(f"Pipeline started: Streaming answer for '{query}'")

        try:
            # The retrieval and reranking steps are identical to the blocking method.
            # They happen fast enough that we don't need to stream them.
            fetch_k = max(20, top_k * 3)
            
            if use_hybrid:
                candidates = await retrieve_hybrid(query, top_k=fetch_k, filters=filters)
            else:
                candidates = retrieve_dense(query, top_k=fetch_k, filters=filters)

            reranker = get_reranker_service()
            top_chunks = reranker.rerank(query, candidates, top_k=top_k)

            context_str, citations = build_context(top_chunks)

            # We yield the citations FIRST, so the UI can render the sources
            # instantly before the LLM even starts typing.
            yield StreamEvent(event="citations", data=citations)

            user_prompt = RAG_USER_PROMPT_TEMPLATE.substitute(
                context_str=context_str,
                query=query
            )

            llm_service = get_llm_service()
            
            # Stream the text chunks as they arrive from Ollama
            async for text_chunk in llm_service.generate_stream(
                system_prompt=RAG_SYSTEM_PROMPT,
                user_prompt=user_prompt
            ):
                yield StreamEvent(event="token", data=text_chunk)

        except Exception as e:
            logger.error(f"Streaming pipeline failed: {e}")
            yield StreamEvent(event="error", data=f"Pipeline Error: {str(e)}")

    async def delete_document(self, document_id: str) -> None:
        """Remove a document from the system completely."""
        try:
            vdb_delete_document(document_id)
            rebuild_bm25_index()
        except Exception as e:
            raise RAGPipelineError(f"Failed to delete document: {str(e)}") from e

    async def list_documents(self) -> List[Dict[str, Any]]:
        """List all ingested documents."""
        try:
            return vdb_list_documents()
        except Exception as e:
            raise RAGPipelineError(f"Failed to list documents: {str(e)}") from e


def get_rag_pipeline() -> RAGPipeline:
    """
    FastAPI Dependency injection provider.
    Ensures we reuse the same pipeline instance across API requests.
    """
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
