import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from src.retriever_agent.pipeline import RetrieverAgent
from src.retriever_agent.vector_search import hybrid_search


class FakeCollection:
    def query(self, **kwargs):
        return {
            "ids": [["c1", "c2"]],
            "documents": [["deep learning architecture", "finance annual report"]],
            "metadatas": [[{}, {}]],
            "distances": [[0.1, 0.2]],
        }

    def get(self, **kwargs):
        return {
            "ids": ["c1", "c2", "c3"],
            "documents": [
                "deep learning architecture",
                "finance annual report",
                "retrieval architecture for rag systems",
            ],
            "metadatas": [{}, {}, {}],
        }


class TestRetrieverAgent(unittest.TestCase):
    def test_hybrid_search_combines_dense_and_sparse(self):
        rows = hybrid_search(
            query="rag architecture",
            query_embedding=[0.1, 0.2],
            collection=FakeCollection(),
            dense_top_k=2,
            sparse_top_k=3,
            hybrid_top_k=3,
            dense_weight=0.6,
            sparse_weight=0.4,
        )
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("hybrid_score", rows[0])

    def test_history_respects_limit(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.yaml"
            cfg_path.write_text(
                yaml.safe_dump(
                    {
                        "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                        "chromadb": {"db_path": "./chroma_db", "collection_name": "documents"},
                        "retriever": {
                            "history_keep": 2,
                            "dense_top_k": 2,
                            "sparse_top_k": 2,
                            "hybrid_top_k": 2,
                            "final_top_k": 1,
                            "dense_weight": 0.6,
                            "sparse_weight": 0.4,
                            "reranker": {"provider": "bge", "model": "BAAI/bge-reranker-base"},
                        },
                    }
                )
            )

            with patch("src.retriever_agent.pipeline.get_collection", return_value=object()), patch(
                "src.retriever_agent.pipeline.embed_query", return_value=[0.1, 0.2]
            ), patch(
                "src.retriever_agent.pipeline.hybrid_search",
                return_value=[
                    {
                        "chunk_id": "c1",
                        "text": "about rag architecture",
                        "metadata": {},
                        "dense_score": 0.7,
                        "sparse_score": 0.6,
                        "hybrid_score": 0.66,
                    }
                ],
            ), patch(
                "src.retriever_agent.pipeline.cross_encoder_rerank",
                return_value=[
                    {
                        "chunk_id": "c1",
                        "text": "about rag architecture",
                        "metadata": {},
                        "dense_score": 0.7,
                        "sparse_score": 0.6,
                        "hybrid_score": 0.66,
                        "rerank_score": 0.95,
                    }
                ],
            ):
                agent = RetrieverAgent(config_path=cfg_path)
                agent.retrieve("q1")
                agent.retrieve("q2")
                agent.retrieve("q3")

            self.assertEqual(len(agent.history), 2)
            self.assertEqual([turn.question for turn in agent.history], ["q2", "q3"])


if __name__ == "__main__":
    unittest.main()