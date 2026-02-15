
"""Cross-encoder reranker for hybrid retrieval candidates."""

from typing import Any, Dict, List


def rerank_with_bge(query: str, candidates: List[Dict[str, Any]], model_name: str) -> List[float]:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is required for BGE reranking. Run: pip install sentence-transformers"
        ) from exc

    model = CrossEncoder(model_name)
    pairs = [[query, c["text"]] for c in candidates]
    scores = model.predict(pairs)
    return [float(score) for score in scores]


def cross_encoder_rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    reranker_config: Dict[str, Any],
    top_k: int,
) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    provider = reranker_config.get("provider", "bge")
    model_name = reranker_config.get("model", "BAAI/bge-reranker-base")

    if provider == "bge":
        scores = rerank_with_bge(query, candidates, model_name)
    else:
        raise RuntimeError(f"Unsupported reranker provider: {provider}")

    ranked = []
    for row, score in zip(candidates, scores):
        ranked.append({**row, "rerank_score": float(score)})

    ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return ranked[:top_k]