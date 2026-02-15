"""Simple embedding generation with Ollama (default) or OpenAI."""

from typing import List

from src.common.embeddings import embed_texts as shared_embed_texts

from .errors import EmbeddingError
from .types import Chunk

def embed_chunks(chunks: List[Chunk], config: dict) -> List[List[float]]:
    """Generate embeddings based on config provider."""
    try:
        texts = [chunk.text for chunk in chunks]
        return shared_embed_texts(texts, config)
    except Exception as e:  # keep module-level error contract
        raise EmbeddingError(str(e)) from e