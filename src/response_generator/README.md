# Response Generator

This module performs **two LLM calls** to produce a grounded response:

1. **Grounding/Query enhancement**: rewrites the user question into a standalone query using session history.
2. **Grounded answer generation**: answers with retrieved chunks only.

## Configuration-driven behavior

Configured via `config.yaml` under `response_generator`:

- `provider`: `ollama` or `openai`
- `model`: chat model name
- `temperature`
- `max_tokens`
- `history_keep`: turns kept per user session
- `metadata_path`: YAML metadata file containing prompt task/instructions/output format

## Metadata-driven prompts

`src/response_generator/metadata/prompts.yaml` contains:

- `grounding_prompt` (`task`, `instructions`, `output`)
- `response_prompt` (`task`, `instructions`, `output`)

Adjusting this file updates prompt behavior without code changes.

## Usage

```python
from src.response_generator import GroundedRAGPipeline

pipeline = GroundedRAGPipeline(config_path="config.yaml")
result = pipeline.ask(session_id="user-123", question="Summarize section 2")

print(result.enhanced_query)
print(result.response)
```
