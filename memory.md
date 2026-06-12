# RAG System — Project Memory

> **Purpose:** This file serves as persistent context across conversations.
> It reduces token usage by capturing all decisions, progress, and lessons learned.
> Always read this file first before making changes to the project.

---

## Project Vision

Build a **production-grade Retrieval-Augmented Generation (RAG) system** from first principles using exclusively free and open-source tools. The primary goal is **deep learning** — understanding how RAG systems are designed, built, optimized, evaluated, and deployed in real-world companies.

**Non-goals:**
- Using LangChain or LlamaIndex (we build everything from scratch)
- Using paid APIs (OpenAI, Anthropic, paid Pinecone)
- Building a minimum viable product (we aim for production quality)

**End result:** A GitHub-ready portfolio project demonstrating mastery of RAG architecture.

---

## Architecture Decisions

### AD-001: No Abstraction Frameworks
- **Decision:** Build all RAG components from scratch without LangChain/LlamaIndex.
- **Rationale:** Learning-focused project. Understanding internals > rapid prototyping.
- **Tradeoff:** More code to write, but complete understanding of every component.

### AD-002: Layered Architecture
- **Decision:** Separate ingestion, embedding, retrieval, re-ranking, and generation into independent layers.
- **Rationale:** Each layer is independently testable, swappable, and scalable. Matches how production RAG systems are built at companies.
- **Pattern:** Clean Architecture — API → Services → Domain Modules → Infrastructure.

### AD-003: Hybrid Retrieval (Dense + Sparse)
- **Decision:** Combine vector similarity search (dense) with BM25 (sparse) using Reciprocal Rank Fusion (RRF).
- **Rationale:** Dense alone misses exact keyword matches; BM25 alone misses semantic meaning. Hybrid provides best recall.
- **Reference:** Used by Elastic, Vespa, and most production search systems.

### AD-004: Two-Stage Retrieval (Retrieve then Re-rank)
- **Decision:** Retrieve top-20 candidates with bi-encoders, then re-score with a cross-encoder to select top-5.
- **Rationale:** Cross-encoders are 100x more accurate but 1000x slower. Two-stage gives accuracy without latency.
- **Pattern:** Used by Google Search, Bing, and all major search engines.

### AD-005: Qdrant as Vector Database
- **Decision:** Use Qdrant over ChromaDB, Weaviate, and Milvus.
- **Rationale:** Best metadata filtering, excellent performance, great Docker support, Apache 2.0 license.
- **Deployment:** Docker container with persistent volume.

### AD-006: Local LLM via Ollama
- **Decision:** Use Ollama for local LLM inference (Llama 3.1, Mistral, Qwen).
- **Rationale:** Zero cost, full data privacy, no rate limits, works offline.
- **Tradeoff:** Slower than cloud APIs, requires decent hardware (8GB+ RAM).

### AD-007: Singleton Embedding Service
- **Decision:** Load embedding models once, reuse across application lifecycle.
- **Rationale:** Model loading takes 500ms-3s. Repeated loading would make the system unusable.
- **Pattern:** Singleton with lazy initialization.

### AD-008: Four Chunking Strategies
- **Decision:** Implement Fixed, Recursive, Semantic, and Parent-Child chunking.
- **Rationale:** Learning-focused — each strategy has different tradeoffs. Recursive is the default for production.
- **Default:** Recursive chunking (chunk_size=512, overlap=50).

### AD-009: Pydantic Settings for Configuration
- **Decision:** Use Pydantic Settings v2 for type-safe environment variable management.
- **Rationale:** Validates config at startup (fail fast), provides auto-completion, replaces fragile os.getenv() calls.

### AD-010: FastAPI for API Layer
- **Decision:** Use FastAPI over Flask/Django.
- **Rationale:** Native async support, automatic OpenAPI docs, Pydantic integration, production-grade performance.

### AD-011: Vanilla Frontend Architecture
- **Decision:** Build frontend using HTML5, CSS3, and Vanilla JavaScript (ES6+) without frameworks like React/Vue.
- **Rationale:** Demonstrates deep understanding of DOM manipulation, browser APIs, and state management without relying on abstractions. Ensures ultra-lightweight performance.

### AD-012: Centralized API Layer
- **Decision:** Route all frontend-backend communication through a single `api.js` module.
- **Rationale:** Keeps components clean, ensures consistent error handling, loading states, and simplifies future API changes.

### AD-013: Component-based Vanilla JS
- **Decision:** Structure JS logic modularly by page and feature (e.g., `chat.js`, `upload.js`).
- **Rationale:** Prevents monolithic spaghetti code. Promotes reusability and maintainability matching SOLID principles.

---

## Tech Stack

| Category | Tool | Version | Notes |
|---|---|---|---|
| Language | Python | 3.11+ | Type hints, async/await |
| Web Framework | FastAPI | 0.115+ | Async, auto-docs |
| Embeddings | Sentence-Transformers | 3.0+ | — |
| Default Embed Model | all-MiniLM-L6-v2 | — | 384 dims, 80MB, fast |
| Alt Embed Model | BAAI/bge-small-en-v1.5 | — | 384 dims, better quality |
| Vector Database | Qdrant | 1.12+ | Docker container |
| Sparse Retrieval | rank_bm25 | 0.2.2 | BM25 implementation |
| Re-ranker | BAAI/bge-reranker-base | — | Cross-encoder, 278MB |
| LLM Runtime | Ollama | 0.5+ | Local inference |
| Default LLM | llama3.1:8b | — | General purpose |
| PDF Parsing | PyMuPDF (fitz) | 1.24+ | Fast, accurate |
| DOCX Parsing | python-docx | 1.1+ | — |
| Evaluation | RAGAS | 0.2+ | Industry-standard |
| Logging | Loguru | 0.7+ | Structured logging |
| Testing | pytest | 8.0+ | Unit + integration |
| Config | Pydantic Settings | 2.0+ | Type-safe .env |
| Containerization | Docker + Compose | — | Multi-container |
| CI/CD | GitHub Actions | — | lint, test, build |
| Frontend Core | HTML5, CSS3, JS (ES6+) | — | Vanilla frontend |
| UI/UX | Custom Design System | — | Dark/Light mode, responsive |

---

## Current Progress

### Completed Phases

- [x] **Phase 1: Architecture Design**
  - System architecture with data flow diagrams
  - Technology selection with justifications
  - Component-level architecture for all 8 layers
  - Deployment architecture (Docker Compose)
  - Project folder structure designed
  - memory.md created

- [x] **Phase 2: Project Scaffolding**
  - 23 directories created
  - 17 `__init__.py` files created
  - `app/core/config.py` — Pydantic Settings v2, type-safe env management
  - `app/core/logging.py` — Loguru with console + file + error log handlers
  - `app/core/exceptions.py` — 13 custom exception classes in a hierarchy
  - `app/core/constants.py` — File types, embedding models, retrieval constants
  - `app/main.py` — FastAPI with application factory pattern, lifespan, CORS, health check
  - `.env.example` + `.env` — All 20+ configuration variables documented
  - `.gitignore` — Comprehensive rules for Python/ML/Docker projects
  - `requirements.txt` — 14 production packages with version pinning
  - `requirements-dev.txt` — 6 dev packages (pytest, ruff, mypy)
  - `pyproject.toml` — Ruff + pytest + mypy unified configuration
  - `README.md` — Production-quality with architecture, setup guide, tech stack

- [x] **Phase 3: Ingestion Pipeline**
  - Document loaders (PDF, DOCX, TXT, MD) via `loader.py`
  - Text cleaner for unicode/whitespace via `cleaner.py`
  - Text parser and deterministic ID generator via `parser.py`
  - Chunker strategies (Fixed, Recursive) via `chunker.py` (Semantic/Parent-Child delayed to Phase 4/5)

- [x] **Phase 4: Embedding Layer**
  - Model registry & validation via `models.py`
  - Singleton embedding service using `sentence-transformers` via `service.py`
  - Batch processing and vector normalization implemented

- [x] **Phase 5: Vector Database Layer**
  - Qdrant singleton connection manager via `client.py` (with gRPC support)
  - Collection creation with HNSW and payload indexing via `collections.py`
  - Upsert (UUID conversion) and vector search operations via `operations.py`

- [x] **Phase 6: Retrieval Layer**
  - Standardized metadata filtering via `filters.py` (Pydantic schemas)
  - Semantic vector search via `dense.py`
  - In-memory BM25 index via `sparse.py`
  - Async hybrid retrieval and Reciprocal Rank Fusion via `hybrid.py`

- [x] **Phase 7: Re-ranking Layer**
  - Two-Stage Retrieval architecture implemented
  - Singleton `CrossEncoder` service via `reranker.py`

- [x] **Phase 8: Generation Layer**
  - Prompt templates with strict boundaries via `prompts.py`
  - Context and citation builder via `context.py`
  - Async Ollama client wrapper with streaming via `llm.py`

- [x] **Phase 9: API Layer**
  - Pydantic models for request/response validation via `models.py`
  - FastAPI endpoints for ingestion via `ingestion.py`
  - Search endpoints with Server-Sent Events (SSE) streaming via `search.py`
  - Global router integration via `router.py`

- [x] **Phase 10: RAG Pipeline Orchestrator**
  - End-to-end `ingest_document()` workflow
  - End-to-end `answer_question()` workflow (with and without streaming)
  - Clean separation of business logic from API layer

- [x] **Phase 11: Main Application & Startup**
  - `main.py` entry point
  - FastApi Lifespan context manager to preload ML models and verify DB
  - Global exception handling and CORS

- [x] **Phase 12: Deployment & Testing (Final Polish)**
  - `docker-compose.yml` configured for Qdrant and API
  - `Dockerfile` created for production API deployment
  - Final architectural review

### Current Phase

- [x] **Frontend Architecture Complete!**

---

## Frontend Pending Tasks

### Phase 1: UI Architecture
- [x] Design System (Colors, Typography, Components)
- [x] Page Wireframes layout strategy
- [x] Folder structure scaffolding

### Phase 2: HTML Structure
- [x] index.html (Dashboard)
- [x] chat.html / ask.html (Main RAG interface)
- [x] upload.html (Document management)
- [x] search.html (Retrieval results)
- [x] analytics.html (Performance dashboards)
- [x] settings.html (Configuration)

### Phase 3: CSS System
- [x] main.css (Variables, resets, utilities)
- [x] Component specific CSS (dashboard, chat, upload, analytics)
- [x] Responsive design & Dark mode

### Phase 4: JavaScript Architecture
- [x] config.js & utils.js
- [x] chat.js (Streaming, Markdown, Auto-scroll)
- [x] upload.js (Drag & Drop, validation)
- [x] analytics.js (Vanilla JS charts)

### Phase 5: API Integration
- [x] api.js module (Centralized fetch wrapper)
- [x] Hook up health, ingest, search, ask endpoints

### Phase 6: Testing & Optimization
- [x] Edge cases, error notifications
- [x] Performance audits
- [x] README.md updates for recruiters

---

## Backend Pending Tasks
- None. The backend is fully built from scratch using clean architecture!

### Phase 4: Embedding Layer
- [x] Embedding service (singleton)
- [x] Model registry and comparison utilities
- [x] Batch embedding support

### Phase 5: Vector Database Layer
- [x] Qdrant connection manager
- [x] Collection CRUD operations
- [x] Search and filter operations

### Phase 6: Retrieval Layer
- [x] Dense retrieval (vector similarity)
- [x] Sparse retrieval (BM25)
- [x] Hybrid retrieval (RRF)
- [x] Metadata filtering

### Phase 7: Re-ranking Layer
- [x] Cross-encoder re-ranker
- [x] Score normalization

### Phase 8: Generation Layer
- [x] Ollama client wrapper
- [x] Prompt templates
- [x] Context builder

### Phase 9: RAG Pipeline & API
- [x] End-to-end pipeline orchestration
- [x] FastAPI endpoints (health, upload, search, ask)
- [x] Request/response schemas
- [x] Ingestion and query services

### Phase 10: Evaluation
- [x] RAGAS integration
- [x] Evaluation scripts
- [x] Custom metrics

### Phase 11: Testing
- [x] Unit tests for all modules
- [x] Integration tests for pipelines
- [x] Test fixtures and conftest

### Phase 12: Deployment
- [x] Dockerfile
- [x] docker-compose.yml
- [x] GitHub Actions workflows (lint, test, build)
- [x] Production README with setup instructions

---

## Known Issues

- **WSL2/Docker Hanging on Windows Home:** `docker-compose up` resulted in `Bad Gateway` and hanging named pipes. We bypassed this by re-configuring the project to run entirely natively using Qdrant's local file storage (`path` parameter instead of `host/port`) and installing dependencies locally.

---

## Lessons Learned

### L-001: Build From Scratch for Learning
Building without LangChain/LlamaIndex forces you to understand every design decision. This is harder but produces much deeper understanding. In production, you might use frameworks — but only after understanding what they abstract away.

### L-002: Architecture First, Code Second
Spending time on architecture design before writing code prevents costly rewrites. Production teams typically spend 20-30% of project time on design.

### L-003: The Two-Stage Retrieval Pattern
The retrieve-then-rerank pattern is universally used in production search systems. It's the key insight that separates prototype RAG from production RAG.

---

## Project Location

```
c:\Users\jasme\.gemini\antigravity\scratch\rag-system\
```

## Key File Paths

| File | Purpose |
|---|---|
| `memory.md` | This file — project context |
| `app/main.py` | FastAPI entry point |
| `app/core/config.py` | All configuration |
| `app/pipeline/rag_pipeline.py` | End-to-end RAG orchestration |
| `docker-compose.yml` | Multi-container deployment |
| `.env` | Environment variables (not committed) |
