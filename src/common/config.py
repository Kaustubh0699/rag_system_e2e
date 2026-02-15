"""Shared config loader for RAG modules."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "embedding": {
        "provider": "ollama",
        "model": "nomic-embed-text",
    },
    "ollama": {
        "base_url": "http://localhost:11434",
    },
    "chromadb": {
        "db_path": "./chroma_db",
        "collection_name": "documents",
    },
    "chunking": {
        "chunk_size_tokens": 1000,
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
        },
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

    return config