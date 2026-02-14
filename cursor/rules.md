# Cursor Rules — Assetized RAG System

## Goal
Build a RAG system with graph-based reranking later. For now, implement modules one at a time.
The codebase must be *assetized*: each component is independent and composable.

## Repository layout
- `src/`
  - `<asset_name>/`
    - `__init__.py` (public API exports)
    - `interfaces.py` (protocols / abstract interfaces)
    - `models.py` (dataclasses/pydantic models)
    - `config.py` (settings)
    - `errors.py` (custom exceptions)
    - `impl/` (implementation details)
    - `README.md` (how to use this asset)
    - `tests/` (unit tests for this asset)

## Cross-asset principles
- Assets should depend on interfaces, not implementations.
- Assets should be swappable (e.g., embedding provider, chunker strategy, storage backend).
- Avoid circular dependencies between assets.
- Keep IO boundaries explicit (input/output models).

## Naming
- Use snake_case for packages and files.
- Use explicit names (e.g., `chunking`, `embedding`, `storage`).

## Tests
- Pytest.
- Test public APIs, not private helpers.
- Include at least:
  - happy path
  - one failure case (raises correct exception)

## Current focus
We will implement modules in this order:
1) `chunk_embed_store` (chunk + embed + store)
2) retrieval
3) graph reranker
4) conversation memory/context manager
5) API layer

Cursor should only work on the current module unless asked otherwise.
