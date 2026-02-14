"""Simple config loader from config.yaml."""

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(config_path: str | Path = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = Path(config_path)
    
    if not config_path.exists():
        # Return defaults if config doesn't exist
        return {
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
        }
    
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Allow environment variable override for OpenAI API key
    if "embedding" in config and config["embedding"].get("provider") == "openai":
        if "api_key" not in config["embedding"]:
            config["embedding"]["api_key"] = os.getenv("OPENAI_API_KEY", "")
    
    return config
