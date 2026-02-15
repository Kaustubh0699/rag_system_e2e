"""Hybrid search (dense + sparse BM25-style) against ChromaDB."""

import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import chromadb
from chromadb.config import Settings

from src.common.config import get_effective_collection_name

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "to", "of", "in", "on", "for", "with", "and", "or", "by", "as", "at", "be", "it", "this", "that",
}


def tokenize(text: str) -> List[str]:
    raw = [t.strip(".,!?;:()[]{}\"'`").lower() for t in text.split()]
    return [t for t in raw if t and t not in STOPWORDS]


def get_collection(config: dict):
    chromadb_config = config.get("chromadb", {})
    db_path = Path(chromadb_config.get("db_path", "./chroma_db")).resolve()
    collection_name = get_effective_collection_name(config)

    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(name=collection_name)


def dense_search(query_embedding: List[float], collection: Any, top_k: int) -> List[Dict[str, Any]]:
    response = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    ids = response.get("ids", [[]])[0]
    docs = response.get("documents", [[]])[0]
    metadatas = response.get("metadatas", [[]])[0]
    distances = response.get("distances", [[]])[0]

    rows = []
    for chunk_id, text, metadata, distance in zip(ids, docs, metadatas, distances):
        rows.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "metadata": metadata or {},
                "dense_score": 1.0 / (1.0 + float(distance)),
            }
        )
    return rows


def sparse_search(query: str, collection: Any, top_k: int) -> List[Dict[str, Any]]:
    all_rows = collection.get(include=["documents", "metadatas"])
    ids = all_rows.get("ids", [])
    docs = all_rows.get("documents", [])
    metas = all_rows.get("metadatas", [])

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    doc_tokens = [tokenize(doc or "") for doc in docs]
    doc_freq: Dict[str, int] = defaultdict(int)
    for toks in doc_tokens:
        for tok in set(toks):
            doc_freq[tok] += 1

    n_docs = max(len(doc_tokens), 1)
    avgdl = (sum(len(toks) for toks in doc_tokens) / n_docs) if n_docs else 1.0
    k1 = 1.5
    b = 0.75

    scored = []
    for chunk_id, text, metadata, toks in zip(ids, docs, metas, doc_tokens):
        if not toks:
            continue
        tf = Counter(toks)
        dl = len(toks)
        score = 0.0
        for q in query_tokens:
            if q not in tf:
                continue
            idf = math.log(1 + ((n_docs - doc_freq.get(q, 0) + 0.5) / (doc_freq.get(q, 0) + 0.5)))
            num = tf[q] * (k1 + 1)
            den = tf[q] + k1 * (1 - b + b * (dl / max(avgdl, 1e-8)))
            score += idf * (num / den)
        if score > 0:
            scored.append(
                {
                    "chunk_id": chunk_id,
                    "text": text,
                    "metadata": metadata or {},
                    "sparse_score": float(score),
                }
            )

    scored.sort(key=lambda x: x["sparse_score"], reverse=True)
    return scored[:top_k]


def hybrid_search(
    query: str,
    query_embedding: List[float],
    collection: Any,
    dense_top_k: int,
    sparse_top_k: int,
    hybrid_top_k: int,
    dense_weight: float,
    sparse_weight: float,
) -> List[Dict[str, Any]]:
    dense_rows = dense_search(query_embedding, collection, dense_top_k)
    sparse_rows = sparse_search(query, collection, sparse_top_k)

    by_id: Dict[str, Dict[str, Any]] = {}
    for row in dense_rows:
        by_id[row["chunk_id"]] = {**row, "sparse_score": 0.0}
    for row in sparse_rows:
        existing = by_id.get(row["chunk_id"], {"dense_score": 0.0})
        by_id[row["chunk_id"]] = {
            **existing,
            **row,
            "dense_score": existing.get("dense_score", 0.0),
        }

    results = []
    for row in by_id.values():
        hybrid_score = (dense_weight * float(row.get("dense_score", 0.0))) + (
            sparse_weight * float(row.get("sparse_score", 0.0))
        )
        results.append({**row, "hybrid_score": hybrid_score})

    results.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return results[:hybrid_top_k]