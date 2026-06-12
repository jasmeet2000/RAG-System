"""
Sparse Retrieval — Keyword/Exact Match search using BM25.

=== WHY THIS FILE EXISTS ===
Dense embeddings are great for semantics ("financial performance" -> "revenue"),
but they are TERRIBLE at exact keyword matches.
If you search for a specific product ID "XJ-9000" or a unique name "Elon Musk",
dense vectors often completely miss it because those specific terms get averaged out.

BM25 (Best Matching 25) is the industry standard algorithm for keyword search
(it powers Elasticsearch, Solr, Lucene). It relies on term frequency-inverse
document frequency (TF-IDF).

=== PRODUCTION CONSIDERATION ===
In a real production system, BM25 is handled directly by the database
(e.g., Elasticsearch, or Qdrant's new Sparse Vectors feature utilizing SPLADE).
For this learning project, we implement an in-memory BM25 index using the
`rank_bm25` library. This is extremely fast for thousands of documents, but
would not scale to millions without distributing the index.

=== HOW IT INTERACTS WITH OTHER MODULES ===
  Caller:  app/retrieval/hybrid.py
  Uses:    rank_bm25 library, nltk/re for tokenization
"""

import string
from typing import List, Dict, Optional, Any

from rank_bm25 import BM25Okapi

from app.core.exceptions import RetrievalError
from app.core.logging import get_logger
from app.retrieval.filters import DocumentFilter
from app.retrieval.dense import RetrievedChunk
from app.vectordb.client import get_qdrant_client
from app.core.config import settings

logger = get_logger(__name__)

# Singleton to hold the in-memory index
_bm25_index: Optional["BM25Index"] = None


class BM25Index:
    """
    Manages an in-memory BM25 search index over the document chunks.
    """

    def __init__(self):
        self.corpus_payloads: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None
        self._build_index()

    def _tokenize(self, text: str) -> List[str]:
        """
        Convert text to tokens for BM25.
        Lowercases, removes punctuation, and splits on whitespace.
        In production, use a stemming tokenizer (like NLTK Snowball).
        """
        text = text.lower()
        # Remove punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))
        return text.split()

    def _build_index(self) -> None:
        """
        Pulls all chunks from Qdrant to build the in-memory BM25 index.
        Note: This is an expensive startup operation for large datasets.
        """
        logger.info("Building BM25 in-memory index from Qdrant payloads...")
        client = get_qdrant_client()
        
        try:
            # Scroll through the entire collection to fetch all payloads
            records, next_page = client.scroll(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )
            
            # Continue scrolling if there are more than 10k records
            all_records = records
            while next_page is not None:
                records, next_page = client.scroll(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    limit=10000,
                    offset=next_page,
                    with_payload=True,
                    with_vectors=False,
                )
                all_records.extend(records)

            if not all_records:
                logger.warning("Qdrant collection is empty. BM25 index will be empty.")
                self.corpus_payloads = []
                self.bm25 = None
                return

            self.corpus_payloads = [r.payload for r in all_records if r.payload]
            
            # Tokenize the entire corpus
            tokenized_corpus = [
                self._tokenize(p.get("content", "")) for p in self.corpus_payloads
            ]
            
            self.bm25 = BM25Okapi(tokenized_corpus)
            logger.info(f"BM25 index built with {len(self.corpus_payloads)} chunks.")

        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            self.corpus_payloads = []
            self.bm25 = None

    def search(
        self, query: str, top_k: int = 10, filters: Optional[DocumentFilter] = None
    ) -> List[RetrievedChunk]:
        """Perform BM25 search over the in-memory corpus."""
        if not self.bm25 or not self.corpus_payloads:
            logger.warning("BM25 index is empty. Returning no results.")
            return []

        tokenized_query = self._tokenize(query)
        # get_scores returns a numpy array of scores corresponding to corpus indices
        doc_scores = self.bm25.get_scores(tokenized_query)

        # Pair scores with payloads and sort
        scored_docs = list(zip(doc_scores, self.corpus_payloads))
        
        # Apply metadata filtering manually since this is in-memory
        if filters:
            filter_dict = filters.to_dict()
            filtered_docs = []
            for score, payload in scored_docs:
                match = True
                for key, val in filter_dict.items():
                    if payload.get(key) != val:
                        match = False
                        break
                if match:
                    filtered_docs.append((score, payload))
            scored_docs = filtered_docs

        # Sort descending by score
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Take top_k
        top_docs = scored_docs[:top_k]

        results = []
        for score, payload in top_docs:
            if score <= 0.0:  # BM25 scores can be 0 if no tokens match
                continue
                
            results.append(
                RetrievedChunk(
                    chunk_id=payload.get("chunk_id", "unknown"),
                    document_id=payload.get("document_id", "unknown"),
                    content=payload.get("content", ""),
                    score=float(score),
                    metadata={k: v for k, v in payload.items() if k not in ["content", "chunk_id", "document_id"]},
                    source_type="sparse",
                )
            )

        return results


def get_bm25_index() -> BM25Index:
    """Singleton accessor for the BM25 index."""
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = BM25Index()
    return _bm25_index


def rebuild_bm25_index() -> None:
    """Force rebuild of the index (call this after ingestion)."""
    global _bm25_index
    _bm25_index = BM25Index()


def retrieve_sparse(
    query: str,
    top_k: int = 10,
    filters: Optional[DocumentFilter] = None
) -> List[RetrievedChunk]:
    """
    Public API for sparse retrieval.
    """
    if not query.strip():
        return []

    try:
        index = get_bm25_index()
        return index.search(query, top_k=top_k, filters=filters)
    except Exception as e:
        logger.error(f"Sparse retrieval failed: {e}")
        raise RetrievalError(f"Failed to perform sparse retrieval: {str(e)}") from e
