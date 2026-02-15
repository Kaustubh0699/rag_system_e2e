
"""Cross-encoder reranker for hybrid retrieval candidates."""

import os
from typing import Any, Dict, List


def rerank_with_bge(
    query: str,
    candidates: List[Dict[str, Any]],
    model_name: str,
    local_files_only: bool = True,
) -> List[float]:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is required for BGE reranking. Run: pip install sentence-transformers"
        ) from exc

    # Avoid network calls when offline: use cache only (run once online to download model)
    if local_files_only:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    model = CrossEncoder(model_name, local_files_only=local_files_only)
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
    local_files_only = reranker_config.get("local_files_only", True)

    if provider == "bge":
        scores = rerank_with_bge(query, candidates, model_name, local_files_only=local_files_only)
    else:
        raise RuntimeError(f"Unsupported reranker provider: {provider}")

    ranked = []
    for row, score in zip(candidates, scores):
        ranked.append({**row, "rerank_score": float(score)})

    ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return ranked[:top_k]