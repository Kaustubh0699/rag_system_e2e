"""Shared config loader for RAG modules."""

import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml


def get_effective_collection_name(config: Dict[str, Any]) -> str:
    """Return ChromaDB collection name, optionally scoped by embedding model to avoid dimension mismatch.

    When embedding model changes (e.g. mxbai-embed-large 1024 dim vs nomic-embed-text 768 dim),
    using a different collection per model avoids 'expecting dimension X, got Y' errors.
    """
    chroma = config.get("chromadb", {})
    base = chroma.get("collection_name", "documents")
    if not chroma.get("embedding_scoped_collection", True):
        return base
    model = (config.get("embedding", {}).get("model") or "").strip()
    if not model:
        return base
    # Sanitize for ChromaDB collection name: alphanumeric and underscore only
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", model).strip("_") or "default"
    return f"{base}_{safe}"


DEFAULT_CONFIG: Dict[str, Any] = {
    "embedding": {
        "provider": "ollama",
        "model": "nomic-embed-text",
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
    },
    "chromadb": {
        "db_path": "./chroma_db",
        "collection_name": "documents",
        "embedding_scoped_collection": True,
    },
    "chunking": {
        "chunk_size_tokens": 512,
        "overlap_sentences": 2,
    },
    "retriever": {
        "history_keep": 5,
        "dense_top_k": 20,
        "sparse_top_k": 20,
        "hybrid_top_k": 30,
        "final_top_k": 5,
        "score_threshold": 0.0,
        "dense_weight": 0.6,
        "sparse_weight": 0.4,
        "reranker": {
            "provider": "bge",
            "model": "BAAI/bge-reranker-base",
            "local_files_only": True,
        },
    },
    "response_generator": {
        "provider": "ollama",
        "model": "llama3.2",
        "temperature": 0.2,
        "max_tokens": 512,
        "history_keep": 10,
        "metadata_path": "src/response_generator/metadata/prompts.yaml",
    },
}


def load_config(config_path: str | Path = "config.yaml") -> Dict[str, Any]:
    config_path = Path(config_path)
    if not config_path.exists():
        return DEFAULT_CONFIG.copy()

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if "embedding" in config and config["embedding"].get("provider") == "openai":
        if "api_key" not in config["embedding"]:
            config["embedding"]["api_key"] = os.getenv("OPENAI_API_KEY", "")
    if "response_generator" in config and config["response_generator"].get("provider") == "openai":
        if "api_key" not in config["response_generator"]:
            config["response_generator"]["api_key"] = os.getenv("OPENAI_API_KEY", "")
    return config