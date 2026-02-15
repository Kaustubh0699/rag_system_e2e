import unittest

from src.response_generator.pipeline import ResponseGenerator


class ResponseGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.generator = ResponseGenerator(config_path="config.yaml")

    def test_generate_uses_two_llm_calls_and_tracks_session_history(self):
        calls = []

        def fake_call(prompt: str) -> str:
            calls.append(prompt)
            if len(calls) == 1:
                return "standalone rewritten query"
            return "Grounded answer from chunks [chunk_1]"

        self.generator._call_llm = fake_call  # type: ignore[method-assign]

        response = self.generator.generate(
            session_id="session-a",
            question="What does it say about latency?",
            retrieved_chunks=[{"chunk_id": "chunk_1", "text": "Latency target is 200ms."}],
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(response.enhanced_query, "standalone rewritten query")
        self.assertIn("[chunk_1]", response.response)
        self.assertEqual(len(self.generator.session_histories["session-a"]), 1)

    def test_session_history_is_trimmed_to_history_keep(self):
        self.generator.history_keep = 2
        self.generator._call_llm = lambda _: "ok"  # type: ignore[method-assign]

        for idx in range(3):
            self.generator.generate(
                session_id="session-b",
                question=f"q{idx}",
                retrieved_chunks=[{"chunk_id": f"chunk_{idx}", "text": "ctx"}],
            )

        turns = self.generator.session_histories["session-b"]
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0].user_question, "q1")
        self.assertEqual(turns[1].user_question, "q2")


if __name__ == "__main__":
    unittest.main()
