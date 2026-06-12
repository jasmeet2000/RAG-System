"""
Qdrant Connection Manager — Singleton client for the Vector Database.

=== WHY THIS FILE EXISTS ===
Like the embedding model, establishing a database connection takes time
and requires network handshakes (TCP/gRPC). Creating a new connection
for every API request would crush database performance.

This module implements the Singleton pattern for the QdrantClient.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/vectordb/collections.py, app/vectordb/operations.py
  Uses:    qdrant_client, app.core.config

=== INDUSTRY ALTERNATIVES ===
- Connection Pooling: For massive traffic, you'd use a connection pool
  rather than a single client instance. However, QdrantClient handles
  connection reuse natively under the hood.

=== DESIGN DECISIONS ===
- REST vs gRPC: Qdrant supports both. We configure the client to use gRPC
  for heavy operations (like batch upserts) because it's significantly faster
  and has lower serialization overhead than HTTP/REST.
"""

from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import settings
from app.core.exceptions import VectorDBConnectionError
from app.core.logging import get_logger

logger = get_logger(__name__)

# The singleton instance
_qdrant_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """
    Get or create the singleton QdrantClient.

    This client automatically manages connection pools internally.
    It prefers gRPC if the port is configured, falling back to REST.
    """
    global _qdrant_client

    if _qdrant_client is None:
        logger.info(f"Connecting to Qdrant Vector Database at {settings.qdrant_url}")
        try:
            _qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                grpc_port=settings.QDRANT_GRPC_PORT,
                prefer_grpc=True,
            )
            # Ping the server to verify connection immediately
            _qdrant_client.get_collections()
            logger.info("Successfully connected to Qdrant.")
        except Exception as e:
            _qdrant_client = None
            raise VectorDBConnectionError(
                "Failed to connect to Qdrant Vector Database.",
                detail=str(e),
            ) from e

    return _qdrant_client


def verify_connection() -> bool:
    """
    Check if Qdrant is accessible. Useful for the FastAPI /health endpoint.
    """
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")
        return False
