"""Retriever agent: embed query -> hybrid search -> cross-encoder rerank -> keep history."""

import os
from pathlib import Path
from typing import List

from .config_loader import load_config
from .embedder import embed_query
from .reranker import cross_encoder_rerank
from .types import QueryTurn, RetrievalResult, RetrievedChunk
from .vector_search import get_collection, hybrid_search


class RetrieverAgent:
    def __init__(self, config_path: str | Path = "config.yaml"):
        self.config = load_config(config_path)
        retriever_config = self.config.get("retriever", {})

        # Set HF offline before any reranker import (avoids getaddrinfo when offline)
        reranker_cfg = retriever_config.get("reranker", {})
        if reranker_cfg.get("local_files_only", True):
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        self.history_keep = int(retriever_config.get("history_keep", 5))
        self.dense_top_k = int(retriever_config.get("dense_top_k", 20))
        self.sparse_top_k = int(retriever_config.get("sparse_top_k", 20))
        self.hybrid_top_k = int(retriever_config.get("hybrid_top_k", 30))
        self.final_top_k = int(retriever_config.get("final_top_k", 5))
        self.score_threshold = float(retriever_config.get("score_threshold", 0.0))
        self.dense_weight = float(retriever_config.get("dense_weight", 0.6))
        self.sparse_weight = float(retriever_config.get("sparse_weight", 0.4))
        self.reranker_config = retriever_config.get(
            "reranker",
            {"provider": "bge", "model": "BAAI/bge-reranker-base"},
        )

        self.history: List[QueryTurn] = []
        self.collection = get_collection(self.config)

    def retrieve(self, question: str) -> RetrievalResult:
        query_embedding = embed_query(question, self.config)
        candidates = hybrid_search(
            query=question,
            query_embedding=query_embedding,
            collection=self.collection,
            dense_top_k=self.dense_top_k,
            sparse_top_k=self.sparse_top_k,
            hybrid_top_k=self.hybrid_top_k,
            dense_weight=self.dense_weight,
            sparse_weight=self.sparse_weight,
        )
        ranked = cross_encoder_rerank(
            query=question,
            candidates=candidates,
            reranker_config=self.reranker_config,
            top_k=self.final_top_k,
        )

        # Apply score threshold: keep only chunks with rerank_score >= threshold
        if self.score_threshold is not None and self.score_threshold > 0:
            ranked = [row for row in ranked if float(row.get("rerank_score", 0)) >= self.score_threshold]

        self.history.append(QueryTurn(question=question))
        if len(self.history) > self.history_keep:
            self.history = self.history[-self.history_keep :]

        chunks = [RetrievedChunk(**row) for row in ranked]
        return RetrievalResult(question=question, chunks=chunks)