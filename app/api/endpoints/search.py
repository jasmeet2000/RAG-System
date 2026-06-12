"""
Search Endpoints — Handles user queries and LLM generation.

=== WHY THIS FILE EXISTS ===
This file exposes the core value of the RAG system to the outside world.
It receives a user's question, passes it to the Orchestrator Pipeline (Phase 10),
and streams the AI's answer back to the frontend.

=== INDUSTRY UX PATTERN: Server-Sent Events (SSE) ===
The `ask_question` endpoint supports streaming via Server-Sent Events.
Instead of sending a standard JSON response, we return a `StreamingResponse`
that keeps the HTTP connection open and yields data chunks as the LLM generates
them. This gives the user instant visual feedback (the "typing" effect).
"""

import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.models import SearchRequest, SearchResponse, StreamEvent
from app.core.logging import get_logger

# We will build the RAG Pipeline in Phase 10 to orchestrate the actual logic
from app.pipeline.rag_pipeline import RAGPipeline, get_rag_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])


async def sse_format(generator: AsyncGenerator[StreamEvent, None]) -> AsyncGenerator[str, None]:
    """
    Format our internal StreamEvent objects into the standard Server-Sent Events format.
    SSE format requires: `data: {json_string}\n\n`
    """
    try:
        async for event in generator:
            # We dump the Pydantic model to JSON
            yield f"data: {event.model_dump_json()}\n\n"
    except Exception as e:
        logger.error(f"SSE Streaming error: {e}")
        error_event = StreamEvent(event="error", data=str(e))
        yield f"data: {error_event.model_dump_json()}\n\n"
    finally:
        # Always yield a 'done' event so the frontend knows to close the connection
        done_event = StreamEvent(event="done", data="")
        yield f"data: {done_event.model_dump_json()}\n\n"


@router.post("", response_model=SearchResponse)
async def ask_question(
    request: Request,
    payload: SearchRequest,
    pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """
    Ask a question against the ingested document knowledge base.
    
    If `stream=True` (the default), this endpoint returns a StreamingResponse
    of Server-Sent Events (text/event-stream).
    If `stream=False`, it waits for the LLM to finish and returns a complete JSON response.
    """
    logger.info(f"Received search query: '{payload.query}' (Stream: {payload.stream})")
    start_time = time.perf_counter()

    try:
        if payload.stream:
            # Generate an async generator from the pipeline
            raw_generator = pipeline.answer_question_stream(
                query=payload.query,
                top_k=payload.top_k,
                filters=payload.filters,
                use_hybrid=payload.hybrid_search,
            )
            
            # Wrap it in SSE formatting and return a StreamingResponse
            return StreamingResponse(
                sse_format(raw_generator),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            # Blocking mode (wait for full generation)
            answer, citations = await pipeline.answer_question(
                query=payload.query,
                top_k=payload.top_k,
                filters=payload.filters,
                use_hybrid=payload.hybrid_search,
            )
            
            elapsed = time.perf_counter() - start_time
            
            return SearchResponse(
                answer=answer,
                citations=citations,
                processing_time_sec=round(elapsed, 2)
            )

    except Exception as e:
        logger.error(f"Search endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
