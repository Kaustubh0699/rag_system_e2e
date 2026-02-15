"""LLM-backed response generation with history-aware grounding and chunk-grounded answering."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List
import yaml

from .config_loader import load_config
from .types import ConversationTurn, GroundedResponse


class ResponseGeneratorError(Exception):
    pass


class ResponseGenerator:
    def __init__(self, config_path: str | Path = "config.yaml"):
        self.config = load_config(config_path)
        response_config = self.config.get("response_generator", {})

        self.provider = response_config.get("provider", "ollama")
        self.model = response_config.get("model", "llama3.2")
        self.temperature = float(response_config.get("temperature", 0.2))
        self.max_tokens = int(response_config.get("max_tokens", 512))
        self.history_keep = int(response_config.get("history_keep", 10))
        self.metadata_path = Path(
            response_config.get(
                "metadata_path",
                "src/response_generator/metadata/prompts.yaml",
            )
        )

        self.metadata = self._load_metadata(self.metadata_path)
        self.session_histories: Dict[str, List[ConversationTurn]] = {}

    def generate(self, session_id: str, question: str, retrieved_chunks: Iterable[Any]) -> GroundedResponse:
        chunk_rows = [self._normalize_chunk(chunk) for chunk in retrieved_chunks]
        history = self.session_histories.get(session_id, [])

        enhanced_query = self._ground_question(question, history)
        response_text = self._generate_grounded_answer(question, enhanced_query, chunk_rows)

        history.append(
            ConversationTurn(
                user_question=question,
                enhanced_query=enhanced_query,
                assistant_response=response_text,
            )
        )
        self.session_histories[session_id] = history[-self.history_keep :]

        return GroundedResponse(
            session_id=session_id,
            user_question=question,
            enhanced_query=enhanced_query,
            response=response_text,
            context_chunk_ids=[row["chunk_id"] for row in chunk_rows],
        )
    def generate_stream(
        self,
        session_id: str,
        question: str,
        retrieved_chunks: Iterable[Any],
    ) -> Generator[str, None, GroundedResponse]:
        chunk_rows = [self._normalize_chunk(chunk) for chunk in retrieved_chunks]
        history = self.session_histories.get(session_id, [])

        enhanced_query = self._ground_question(question, history)
        response_parts: List[str] = []
        for token in self._stream_grounded_answer(question, enhanced_query, chunk_rows):
            response_parts.append(token)
            yield token

        response_text = "".join(response_parts).strip()
        history.append(
            ConversationTurn(
                user_question=question,
                enhanced_query=enhanced_query,
                assistant_response=response_text,
            )
        )
        self.session_histories[session_id] = history[-self.history_keep :]

        return GroundedResponse(
            session_id=session_id,
            user_question=question,
            enhanced_query=enhanced_query,
            response=response_text,
            context_chunk_ids=[row["chunk_id"] for row in chunk_rows],
        )
        
        
    def _ground_question(self, question: str, history: List[ConversationTurn]) -> str:
        grounding_meta = self.metadata.get("grounding_prompt", {})
        history_lines = []
        for idx, turn in enumerate(history, 1):
            history_lines.append(f"{idx}. user={turn.user_question}")
            history_lines.append(f"   assistant={turn.assistant_response}")

        history_text = "\n".join(history_lines) if history_lines else "(no prior history)"
        prompt = (
            f"Task: {grounding_meta.get('task', '')}\n"
            f"Instructions:\n{self._format_instructions(grounding_meta.get('instructions', []))}\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Latest user question:\n{question}\n\n"
            f"Output requirement:\n{grounding_meta.get('output', '')}"
        )
        return self._call_llm(prompt).strip()

    def _generate_grounded_answer(
        self,
        question: str,
        enhanced_query: str,
        chunk_rows: List[Dict[str, Any]],
    ) -> str:
        response_meta = self.metadata.get("response_prompt", {})
        chunk_text = "\n\n".join(
            [f"[{row['chunk_id']}] {row['text']}" for row in chunk_rows]
        )
        if not chunk_text:
            chunk_text = "(no retrieved chunks)"

        prompt = (
            f"Task: {response_meta.get('task', '')}\n"
            f"Instructions:\n{self._format_instructions(response_meta.get('instructions', []))}\n"
            f"Original question:\n{question}\n\n"
            f"Enhanced retrieval query:\n{enhanced_query}\n\n"
            f"Retrieved chunks:\n{chunk_text}\n\n"
            f"Output requirement:\n{response_meta.get('output', '')}"
        )
        return self._call_llm(prompt).strip()

    def _stream_grounded_answer(
        self,
        question: str,
        enhanced_query: str,
        chunk_rows: List[Dict[str, Any]],
    ) -> Generator[str, None, None]:
        response_meta = self.metadata.get("response_prompt", {})
        chunk_text = "\n\n".join(
            [f"[{row['chunk_id']}] {row['text']}" for row in chunk_rows]
        )
        if not chunk_text:
            chunk_text = "(no retrieved chunks)"

        prompt = (
            f"Task: {response_meta.get('task', '')}\n"
            f"Instructions:\n{self._format_instructions(response_meta.get('instructions', []))}\n"
            f"Original question:\n{question}\n\n"
            f"Enhanced retrieval query:\n{enhanced_query}\n\n"
            f"Retrieved chunks:\n{chunk_text}\n\n"
            f"Output requirement:\n{response_meta.get('output', '')}"
        )

        if self.provider == "ollama":
            yield from self._call_ollama_stream(prompt)
            return
        if self.provider == "openai":
            yield from self._call_openai_stream(prompt)
            return
        raise ResponseGeneratorError(f"Unknown response generator provider: {self.provider}")


    def _call_llm(self, prompt: str) -> str:
        if self.provider == "ollama":
            return self._call_ollama(prompt)
        if self.provider == "openai":
            return self._call_openai(prompt)
        raise ResponseGeneratorError(f"Unknown response generator provider: {self.provider}")

    def _call_ollama(self, prompt: str) -> str:
        try:
            import ollama
        except ImportError as exc:
            raise ResponseGeneratorError("ollama package not installed. Run: pip install ollama") from exc

        base_url = self.config.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")
        client = ollama.Client(host=base_url)
        options = {"temperature": self.temperature}
        if self.max_tokens:
            options["num_predict"] = self.max_tokens
        response = client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options=options,
        )
        return response["message"]["content"]

    def _call_ollama_stream(self, prompt: str) -> Generator[str, None, None]:
        try:
            import ollama
        except ImportError as exc:
            raise ResponseGeneratorError("ollama package not installed. Run: pip install ollama") from exc

        base_url = self.config.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")
        client = ollama.Client(host=base_url)
        options = {"temperature": self.temperature}
        if self.max_tokens:
            options["num_predict"] = self.max_tokens

        stream = client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options=options,
            stream=True,
        )

        for chunk in stream:
            token = chunk.get("message", {}).get("content", "")
            if token:
                yield token


    def _call_openai(self, prompt: str) -> str:
        response_config = self.config.get("response_generator", {})
        api_key = response_config.get("api_key") or self.config.get("embedding", {}).get("api_key")
        if not api_key:
            raise ResponseGeneratorError("OpenAI API key not found in config or OPENAI_API_KEY env var")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ResponseGeneratorError("openai package not installed. Run: pip install openai") from exc

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""
    
    def _call_openai_stream(self, prompt: str) -> Generator[str, None, None]:
        response_config = self.config.get("response_generator", {})
        api_key = response_config.get("api_key") or self.config.get("embedding", {}).get("api_key")
        if not api_key:
            raise ResponseGeneratorError("OpenAI API key not found in config or OPENAI_API_KEY env var")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ResponseGeneratorError("openai package not installed. Run: pip install openai") from exc

        client = OpenAI(api_key=api_key)
        stream = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )

        for chunk in stream:
            if not chunk.choices:
                continue
            token = chunk.choices[0].delta.content or ""
            if token:
                yield token
                
    @staticmethod
    def _format_instructions(instructions: Any) -> str:
        if isinstance(instructions, list):
            return "\n".join([f"- {item}" for item in instructions])
        return str(instructions)

    @staticmethod
    def _normalize_chunk(chunk: Any) -> Dict[str, Any]:
        if hasattr(chunk, "model_dump"):
            row = chunk.model_dump()
        elif isinstance(chunk, dict):
            row = chunk
        else:
            raise ResponseGeneratorError("Retrieved chunks must be dicts or pydantic models")

        return {
            "chunk_id": str(row.get("chunk_id", "unknown_chunk")),
            "text": str(row.get("text", "")),
            "metadata": row.get("metadata", {}),
        }

    @staticmethod
    def _load_metadata(metadata_path: Path) -> Dict[str, Any]:
        if not metadata_path.exists():
            raise ResponseGeneratorError(f"Metadata file not found: {metadata_path}")

        with metadata_path.open("r", encoding="utf-8") as metadata_file:
            return yaml.safe_load(metadata_file) or {}
