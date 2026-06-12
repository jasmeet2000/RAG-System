"""
API Router — Combines all endpoint modules into a single FastAPI router.

=== WHY THIS FILE EXISTS ===
Instead of registering every route directly on the global `app` object in `main.py`,
we group related endpoints into their own modules (`search.py`, `ingestion.py`).
This file imports all those sub-routers and combines them.

In `main.py`, we only need to write: `app.include_router(api_router)`
"""

from fastapi import APIRouter

from app.api.endpoints import ingestion
from app.api.endpoints import search

api_router = APIRouter()

# Include the ingestion routes (e.g., /documents/upload)
api_router.include_router(ingestion.router)

# Include the search routes (e.g., /search)
api_router.include_router(search.router)
