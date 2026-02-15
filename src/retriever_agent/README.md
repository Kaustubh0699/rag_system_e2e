# Retriever Agent

A hybrid retrieval module that takes a user question and returns the most relevant document chunks using:
1. **Hybrid retrieval**: Combines dense vector search (semantic similarity) with sparse BM25-style scoring (keyword matching)
2. **Cross-encoder reranking**: Uses BGE reranker model to re-rank candidates for better relevance

## Features

- **Dense Vector Search**: Semantic similarity search using embeddings
- **Sparse BM25 Search**: Keyword-based search with BM25 scoring
- **Hybrid Scoring**: Combines dense and sparse scores with configurable weights
- **Reranking**: Cross-encoder reranking using BGE model for final ranking
- **Query History**: Maintains conversation history (configurable)

## Installation

### Prerequisites

1. **Python 3.11+** installed

2. **Install project dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - `chromadb>=0.5.0` - Vector database
   - `pydantic>=2.6` - Data validation
   - `ollama>=0.1.0` - Ollama client (for embeddings)
   - `openai>=1.52.0` - OpenAI client (optional, for OpenAI embeddings)
   - `sentence-transformers>=3.0.0` - BGE reranker model
   - `pyyaml>=6.0.0` - YAML config parsing

3. **Install Ollama** (if using Ollama for embeddings):
   
   **Windows:**
   - Download from [https://ollama.ai/download](https://ollama.ai/download)
   - Run the installer
   - Start Ollama service (usually starts automatically)

   **Linux/macOS:**
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

4. **Download embedding model** (if using Ollama):
   ```bash
   ollama pull nomic-embed-text
   # or
   ollama pull mxbai-embed-large
   ```

5. **Download BGE reranker model** (automatic on first use):
   - The `sentence-transformers` library will automatically download `BAAI/bge-reranker-base` on first use
   - Ensure you have internet connection for the first run
   - Model will be cached locally (~400MB)

### Configuration

Create or update `config.yaml` in your project root:

```yaml
embedding:
  provider: "ollama"  # Options: "ollama" or "openai"
  model: "mxbai-embed-large"  # Ollama model name or OpenAI model
  # For OpenAI:
  # provider: "openai"
  # model: "text-embedding-3-small"
  # api_key: "your-openai-api-key"  # Optional, can use OPENAI_API_KEY env var

ollama:
  base_url: "http://localhost:11434"  # Default Ollama URL

chromadb:
  db_path: "./chroma_db"  # Path to ChromaDB database
  collection_name: "documents"  # Collection name

retriever:
  history_keep: 5  # Number of query turns to keep in history
  dense_top_k: 20  # Number of candidates from dense vector search
  sparse_top_k: 20  # Number of candidates from sparse BM25 search
  hybrid_top_k: 30  # Combined candidates before reranking
  final_top_k: 5  # Number of final chunks returned after reranking
  score_threshold: 0.0  # Minimum rerank score to include (0.0 = no filter; raise to drop low-relevance chunks)
  dense_weight: 0.6  # Weight for dense score in hybrid ranking (0.0-1.0)
  sparse_weight: 0.4  # Weight for sparse score in hybrid ranking (0.0-1.0)
  reranker:
    provider: "bge"  # Only "bge" is supported
    model: "BAAI/bge-reranker-base"  # BGE reranker model name
```

## Usage

### Basic Usage

```python
from src.retriever_agent import RetrieverAgent

# Initialize the retriever agent
agent = RetrieverAgent(config_path="config.yaml")

# Retrieve relevant chunks for a query
result = agent.retrieve("What does the architecture section discuss?")

# Access retrieved chunks
for chunk in result.chunks:
    print(f"Chunk ID: {chunk.chunk_id}")
    print(f"Score: {chunk.rerank_score}")
    print(f"Text: {chunk.text[:100]}...")
    print(f"Metadata: {chunk.metadata}")
    print("---")
```

### Advanced Usage

```python
from src.retriever_agent import RetrieverAgent

agent = RetrieverAgent(config_path="config.yaml")

# Multiple queries (history is maintained)
result1 = agent.retrieve("What is the main topic?")
print(f"Found {len(result1.chunks)} chunks")

result2 = agent.retrieve("Can you elaborate on that?")
print(f"Found {len(result2.chunks)} chunks")

# Access query history
print(f"History length: {len(agent.history)}")
for turn in agent.history:
    print(f"Query: {turn.question}")
```

## How It Works

### 1. Query Embedding
- The query is embedded using the configured embedding provider (Ollama or OpenAI)
- Same embedding model must be used as during document ingestion

### 2. Dense Vector Search
- Searches ChromaDB using cosine similarity on embeddings
- Returns top `dense_top_k` candidates with similarity scores

### 3. Sparse BM25 Search
- Tokenizes query and documents
- Calculates BM25 scores based on term frequency and inverse document frequency
- Returns top `sparse_top_k` candidates with BM25 scores

### 4. Hybrid Scoring
- Combines dense and sparse scores using weighted average:
  ```
  hybrid_score = (dense_weight × dense_score) + (sparse_weight × sparse_score)
  ```
- Merges candidates from both searches
- Returns top `hybrid_top_k` candidates

### 5. Reranking
- Uses BGE cross-encoder reranker to re-score candidates
- Cross-encoder considers query-document pairs for better relevance
- Returns top `final_top_k` chunks sorted by rerank score
- Chunks with `rerank_score` below `score_threshold` (from config) are dropped before building the result

## Configuration Parameters

### Retriever Parameters

- **`history_keep`**: Number of previous queries to keep in memory (default: 5)
- **`dense_top_k`**: Candidates from dense search (default: 20)
- **`sparse_top_k`**: Candidates from sparse search (default: 20)
- **`hybrid_top_k`**: Combined candidates before reranking (default: 30)
- **`final_top_k`**: Final chunks returned (default: 5)
- **`score_threshold`**: Minimum rerank score to include; chunks below this are dropped (default: 0.0; set higher to filter low-relevance results)
- **`dense_weight`**: Weight for dense scores (default: 0.6)
- **`sparse_weight`**: Weight for sparse scores (default: 0.4)

### Reranker Parameters

- **`provider`**: Reranker provider (only "bge" supported)
- **`model`**: BGE model name (default: "BAAI/bge-reranker-base")

## Troubleshooting

### Import Errors

**`ModuleNotFoundError: No module named 'sentence_transformers'`**
```bash
pip install sentence-transformers>=3.0.0
```

**`ModuleNotFoundError: No module named 'chromadb'`**
```bash
pip install chromadb>=0.5.0
```

### Embedding Errors

**`EmbeddingError: ollama package not installed`**
```bash
pip install ollama>=0.1.0
```

**`EmbeddingError: Failed to generate embeddings with Ollama`**
- Ensure Ollama is running: `ollama serve`
- Check if model is downloaded: `ollama list`
- Verify `base_url` in config matches your Ollama instance

### ChromaDB Errors

**`Collection not found`**
- Ensure documents have been ingested first using `chunk_embed_store`
- Check `db_path` in config matches the ingestion path
- Verify `collection_name` matches the collection used during ingestion

### Reranker Errors

**`RuntimeError: sentence-transformers is required`**
```bash
pip install sentence-transformers>=3.0.0
```

**Model download fails:**
- Ensure internet connection for first-time model download
- Check disk space (model is ~400MB)
- Model will be cached in `~/.cache/huggingface/`

**`[Errno 11001] getaddrinfo failed` (offline):**
- The BGE reranker loads from Hugging Face by default. For **offline use**, set `retriever.reranker.local_files_only: true` in `config.yaml` (this is the default). Run **once with internet** to download the model, then the app works without network.
- Use `base_url: "http://127.0.0.1:11434"` for Ollama so no DNS lookup is needed (localhost can trigger getaddrinfo on some setups).

### Performance Issues

**Slow retrieval:**
- Reduce `dense_top_k` and `sparse_top_k` values
- Reduce `hybrid_top_k` before reranking
- Consider using a smaller reranker model

**High memory usage:**
- Reduce `history_keep` value
- Process queries one at a time instead of batching

## Architecture

```
src/retriever_agent/
├── __init__.py          # Module exports
├── pipeline.py          # RetrieverAgent class
├── vector_search.py     # Dense/sparse/hybrid search
├── reranker.py          # BGE reranker
├── embedder.py          # Query embedding (uses common module)
├── config_loader.py     # Config loading (uses common module)
├── types.py             # Pydantic models
└── README.md            # This file
```

**Dependencies:**
- `src.common.config` - Shared config loader
- `src.common.embeddings` - Shared embedding functions
- `chromadb` - Vector database
- `sentence-transformers` - BGE reranker

## Examples

### Example 1: Simple Query

```python
from src.retriever_agent import RetrieverAgent

agent = RetrieverAgent()
result = agent.retrieve("What is machine learning?")

print(f"Query: {result.question}")
print(f"Found {len(result.chunks)} relevant chunks:")
for i, chunk in enumerate(result.chunks, 1):
    print(f"\n{i}. Score: {chunk.rerank_score:.4f}")
    print(f"   Text: {chunk.text[:150]}...")
```

### Example 2: Custom Configuration

```python
from src.retriever_agent import RetrieverAgent

# Use custom config with different parameters
agent = RetrieverAgent(config_path="custom_config.yaml")

# Retrieve with custom settings
result = agent.retrieve("Explain the architecture")

# Access metadata
for chunk in result.chunks:
    if "file_name" in chunk.metadata:
        print(f"From: {chunk.metadata['file_name']}")
    if "page_num" in chunk.metadata:
        print(f"Page: {chunk.metadata['page_num']}")
```

## Integration

The retriever agent integrates with:
- **`chunk_embed_store`**: Uses the same ChromaDB collection created during document ingestion
- **`common.embeddings`**: Uses shared embedding functions for consistency
- **`common.config`**: Uses shared config loader for consistency

Ensure the embedding model and ChromaDB path match between ingestion and retrieval.

## License

Part of the RAG System project.
