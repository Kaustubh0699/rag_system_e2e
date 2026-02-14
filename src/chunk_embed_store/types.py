from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field, ConfigDict


class Document(BaseModel):
    model_config = ConfigDict(extra="allow")

    doc_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StoredChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk: Chunk
    embedding: List[float]
