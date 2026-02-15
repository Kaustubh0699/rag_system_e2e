"""High-level orchestration: retrieve chunks, then generate grounded response."""

from __future__ import annotations

from pathlib import Path

from src.retriever_agent import RetrieverAgent

from .pipeline import ResponseGenerator
from .types import GroundedResponse


class GroundedRAGPipeline:
    def __init__(self, config_path: str | Path = "config.yaml"):
        self.retriever = RetrieverAgent(config_path=config_path)
        self.generator = ResponseGenerator(config_path=config_path)

    def ask(self, session_id: str, question: str) -> GroundedResponse:
        retrieval_result = self.retriever.retrieve(question)
        return self.generator.generate(
            session_id=session_id,
            question=question,
            retrieved_chunks=retrieval_result.chunks,
        )
