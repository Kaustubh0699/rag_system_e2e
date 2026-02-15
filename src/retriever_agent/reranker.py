"""Cross-encoder reranker for hybrid retrieval candidates."""

import os
import threading
from typing import Any, Dict, List

# Load BGE model once per (model_name, local_files_only) and reuse for the process lifetime.
_bge_model_cache: Dict[tuple, Any] = {}
_bge_cache_lock = threading.Lock()


def _get_bge_model(model_name: str, local_files_only: bool) -> Any:
    key = (model_name, local_files_only)
    if key in _bge_model_cache:
        return _bge_model_cache[key]
    with _bge_cache_lock:
        if key in _bge_model_cache:
            return _bge_model_cache[key]
        if local_files_only:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for BGE reranking. Run: pip install sentence-transformers"
            ) from exc
        model = CrossEncoder(model_name, local_files_only=local_files_only)
        _bge_model_cache[key] = model
        return model


def rerank_with_bge(
    query: str,
    candidates: List[Dict[str, Any]],
    model_name: str,
    local_files_only: bool = True,
) -> List[float]:
    model = _get_bge_model(model_name, local_files_only)
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