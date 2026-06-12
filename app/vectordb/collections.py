"""
Qdrant Collection Management.

=== WHY THIS FILE EXISTS ===
A "Collection" in a vector DB is like a "Table" in a relational DB.
Before we can insert vectors, we must create a collection.

Crucially, a collection must be configured with:
1. The EXACT dimensionality of our embeddings (e.g., 384 or 768).
2. The distance metric used for similarity (Cosine, Dot, or Euclidean).

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  Initialization scripts or FastAPI startup
  Uses:    app/vectordb/client.py
           app/embeddings/models.py (to get the correct dimension)

=== WHAT HAPPENS WITHOUT IT ===
If we try to insert a 384-dimensional vector into an unconfigured collection,
Qdrant will reject it.

=== INDUSTRY BEST PRACTICES ===
- Payload Indexing: Vector DBs filter by metadata (e.g., "only PDFs").
  If we don't create indices on these metadata fields, the DB must do a
  full table scan before vector search. We create indices here to make
  hybrid search blazing fast.
"""

from qdrant_client.http import models

from app.core.config import settings
from app.core.constants import HNSW_M, HNSW_EF_CONSTRUCT, VECTOR_DISTANCE_METRIC
from app.core.logging import get_logger
from app.embeddings.models import get_model_config
from app.vectordb.client import get_qdrant_client

logger = get_logger(__name__)


def collection_exists(collection_name: str) -> bool:
    """Check if a collection exists in Qdrant."""
    client = get_qdrant_client()
    collections_response = client.get_collections()
    for collection in collections_response.collections:
        if collection.name == collection_name:
            return True
    return False


def setup_collection(recreate: bool = False) -> None:
    """
    Create the main document collection if it doesn't exist.

    Args:
        recreate: If True, deletes the existing collection and creates a fresh one.
                  DANGEROUS: Drops all data. Useful for development/testing.
    """
    client = get_qdrant_client()
    collection_name = settings.QDRANT_COLLECTION_NAME

    if collection_exists(collection_name):
        if recreate:
            logger.warning(f"Recreating collection '{collection_name}' (dropping all data)")
            client.delete_collection(collection_name=collection_name)
        else:
            logger.info(f"Collection '{collection_name}' already exists. Skipping creation.")
            return

    # Get the embedding dimension for the configured model
    model_config = get_model_config(settings.EMBEDDING_MODEL_NAME)
    dimension = model_config.dimension

    # Map our constant to Qdrant's Distance enum
    # We use Dot product if vectors are normalized (which we do in embeddings/service.py)
    distance_map = {
        "Cosine": models.Distance.COSINE,
        "Dot": models.Distance.DOT,
        "Euclid": models.Distance.EUCLID,
    }
    # Dot product is mathematically faster than Cosine and identical for normalized vectors
    distance = models.Distance.DOT

    logger.info(
        f"Creating collection '{collection_name}' "
        f"(Dim: {dimension}, Metric: DOT, Model: {model_config.name})"
    )

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=dimension,
            distance=distance,
        ),
        # HNSW configuration (Hierarchical Navigable Small World)
        # Controls the speed/accuracy tradeoff of the approximate search
        hnsw_config=models.HnswConfigDiff(
            m=HNSW_M,
            ef_construct=HNSW_EF_CONSTRUCT,
        ),
    )

    # Create Payload Indices for metadata filtering
    # This is critical for production performance. If we filter by `file_type`
    # without an index, Qdrant has to scan every single point.
    logger.info("Creating payload indices for metadata filtering...")
    
    indices = [
        ("file_type", models.PayloadSchemaType.KEYWORD),
        ("source", models.PayloadSchemaType.KEYWORD),
        ("author", models.PayloadSchemaType.KEYWORD),
    ]
    
    for field_name, schema_type in indices:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=schema_type,
        )

    logger.info(f"Collection '{collection_name}' setup complete.")
