"""Simple embedding generation with Ollama (default) or OpenAI."""

import logging
from typing import Any, List

from .errors import EmbeddingError
from .types import Chunk

logger = logging.getLogger(__name__)


def create_ollama_embedder(base_url: str, model: str):
    """Create Ollama client."""
    try:
        import ollama
        return ollama, model, base_url
    except ImportError:
        raise EmbeddingError("ollama package not installed. Run: pip install ollama")


def create_openai_embedder(api_key: str, model: str):
    """Create OpenAI client."""
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key), model
    except ImportError:
        raise EmbeddingError("openai package not installed. Run: pip install openai")


def embed_chunks_ollama(chunks: List[Chunk], model: str, base_url: str) -> List[List[float]]:
    """Generate embeddings using Ollama."""
    try:
        import ollama
        
        embeddings = []
        for chunk in chunks:
            # Ollama client uses OLLAMA_HOST env var or defaults to localhost:11434
            response = ollama.embeddings(model=model, prompt=chunk.text)
            embeddings.append(response["embedding"])
        
        logger.info(f"Generated {len(embeddings)} embeddings using Ollama ({base_url})")
        return embeddings
    except Exception as e:
        raise EmbeddingError(f"Failed to generate embeddings with Ollama: {e}") from e


def embed_chunks_openai(chunks: List[Chunk], client: Any, model: str) -> List[List[float]]:
    """Generate embeddings using OpenAI."""
    try:
        texts = [chunk.text for chunk in chunks]
        response = client.embeddings.create(model=model, input=texts)
        embeddings = [item.embedding for item in response.data]
        logger.info(f"Generated {len(embeddings)} embeddings using OpenAI")
        return embeddings
    except Exception as e:
        raise EmbeddingError(f"Failed to generate embeddings with OpenAI: {e}") from e


def embed_chunks(chunks: List[Chunk], config: dict) -> List[List[float]]:
    """Generate embeddings based on config provider."""
    embedding_config = config.get("embedding", {})
    provider = embedding_config.get("provider", "ollama")
    model = embedding_config.get("model", "nomic-embed-text")
    
    if provider == "ollama":
        ollama_config = config.get("ollama", {})
        base_url = ollama_config.get("base_url", "http://localhost:11434")
        return embed_chunks_ollama(chunks, model, base_url)
    elif provider == "openai":
        api_key = embedding_config.get("api_key", "")
        if not api_key:
            raise EmbeddingError("OpenAI API key not found in config or OPENAI_API_KEY env var")
        client, _ = create_openai_embedder(api_key, model)
        return embed_chunks_openai(chunks, client, model)
    else:
        raise EmbeddingError(f"Unknown embedding provider: {provider}")
