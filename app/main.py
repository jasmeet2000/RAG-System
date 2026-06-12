"""
Main Application Entry Point.

=== WHY THIS FILE EXISTS ===
This is the root of the FastAPI application. It is what Uvicorn runs when you
start the server.

It brings together:
1. The API Routers (Phase 9)
2. Middleware (CORS for frontend communication)
3. Application Lifespan (Startup/Shutdown events)
4. Global Exception Handling

=== INDUSTRY BEST PRACTICE: Lifespan Events ===
In a production AI application, you CANNOT load ML models on the first API request.
The first user would experience a 10+ second timeout.
We use FastAPI's `lifespan` context manager to:
1. Verify database connections.
2. Ensure database schemas/indices exist.
3. Preload all heavy ML models into GPU/RAM.
4. Build the in-memory BM25 index.

Only after all of this completes will FastAPI start accepting HTTP requests.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import get_logger

# Startup dependencies
from app.vectordb.client import verify_connection
from app.vectordb.collections import setup_collection
from app.embeddings.service import get_embedding_service
from app.reranking.reranker import get_reranker_service
from app.retrieval.sparse import rebuild_bm25_index
from app.generation.llm import get_llm_service

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Executes startup logic before the server starts accepting requests,
    and cleanup logic when the server shuts down.
    """
    logger.info("Starting up RAG application...")

    try:
        # 1. Verify Vector Database Connection
        logger.info("Step 1: Verifying Qdrant connection...")
        if not verify_connection():
            logger.error("CRITICAL: Cannot connect to Qdrant. Is the Docker container running?")
            # We don't raise here so the app still starts and can serve health checks,
            # but in strict production, you might want to raise an exception.

        # 2. Setup Vector Database Schema (Idempotent)
        logger.info("Step 2: Setting up Vector DB collections and indices...")
        setup_collection(recreate=False)

        # 3. Preload ML Models into Memory (The Singleton instances)
        logger.info("Step 3: Preloading Machine Learning models (this may take a moment)...")
        get_embedding_service()  # Loads Bi-Encoder
        get_reranker_service()   # Loads Cross-Encoder

        # 4. Build In-Memory Sparse Index
        logger.info("Step 4: Building BM25 keyword index from existing database payloads...")
        rebuild_bm25_index()

        # 5. Verify LLM Engine
        logger.info("Step 5: Verifying Ollama connection and model availability...")
        llm = get_llm_service()
        model_exists = await llm.verify_model_exists()
        if not model_exists:
            logger.warning(
                f"Ollama model '{settings.OLLAMA_MODEL}' not found or Ollama is offline. "
                f"Please run: ollama run {settings.OLLAMA_MODEL}"
            )

        logger.info("Startup complete. RAG Application is ready to serve traffic.")
        
        yield  # The application runs here
        
    except Exception as e:
        logger.error(f"Failed during startup sequence: {e}")
        raise
    finally:
        logger.info("Shutting down RAG application. Cleaning up resources...")
        # Add any teardown logic here (closing DB connections, etc.)


# Create the FastAPI Application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise-grade Retrieval-Augmented Generation API",
    lifespan=lifespan,
)

# Configure CORS (Cross-Origin Resource Sharing)
# Critical if a React/Vue frontend runs on a different port (e.g., localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact domains e.g., ["https://my-app.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the API routes built in Phase 9
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check():
    """Simple health check endpoint for load balancers and Kubernetes probes."""
    # Check Qdrant
    vdb_ok = verify_connection()
    
    # Check Ollama
    try:
        llm = get_llm_service()
        llm_ok = await llm.verify_model_exists()
    except Exception:
        llm_ok = False

    return {
        "status": "ok", 
        "version": settings.APP_VERSION,
        "vector_db": "connected" if vdb_ok else "error",
        "llm": "ready" if llm_ok else "error"
    }


# ── Global Exception Handler ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch any unhandled exceptions in the application and return a clean JSON
    response instead of HTML or silent failures.
    """
    logger.error(f"Unhandled exception on {request.method} {request.url}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "path": str(request.url),
        },
    )
