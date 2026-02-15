from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field, ConfigDict


class QueryTurn(BaseModel):
    model_config = ConfigDict(extra="allow")

    question: str


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    dense_score: float = 0.0
    sparse_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: float


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    question: str
    chunks: List[RetrievedChunk] = Field(default_factory=list)