"""Shared embedding helpers for documents and query text."""

from typing import Any, List


class EmbeddingError(Exception):
    pass


def embed_texts_ollama(texts: List[str], model: str, base_url: str = "http://localhost:11434") -> List[List[float]]:
    try:
        import ollama

        client = ollama.Client(host=base_url)
        return [client.embeddings(model=model, prompt=text)["embedding"] for text in texts]
    except ImportError as exc:
        raise EmbeddingError("ollama package not installed. Run: pip install ollama") from exc


def embed_texts_openai(texts: List[str], client: Any, model: str) -> List[List[float]]:
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def embed_texts(texts: List[str], config: dict) -> List[List[float]]:
    embedding_config = config.get("embedding", {})
    provider = embedding_config.get("provider", "ollama")
    model = embedding_config.get("model", "nomic-embed-text")

    if provider == "ollama":
        ollama_config = config.get("ollama", {})
        base_url = ollama_config.get("base_url", "http://localhost:11434")
        return embed_texts_ollama(texts, model, base_url=base_url)

    if provider == "openai":
        api_key = embedding_config.get("api_key", "")
        if not api_key:
            raise EmbeddingError("OpenAI API key not found in config or OPENAI_API_KEY env var")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingError("openai package not installed. Run: pip install openai") from exc

        client = OpenAI(api_key=api_key)
        return embed_texts_openai(texts, client, model)

    raise EmbeddingError(f"Unknown embedding provider: {provider}")


def embed_query(query: str, config: dict) -> List[float]:
    return embed_texts([query], config)[0]