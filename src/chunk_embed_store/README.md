# Chunk Embed Store

Simple module for chunking PDF and PPT documents and storing them in ChromaDB with embeddings.

## Purpose

This module provides functionality to:
- Parse PDF and **PPTX** files (note: only .pptx format is supported, not old .ppt binary format)
- Chunk documents using hierarchical recursive splitting (paragraphs → lines → sentences → tokens)
- Generate embeddings using Ollama (default) or OpenAI
- Store chunks and embeddings in ChromaDB

**Note on PPT files**: Only `.pptx` format (Office Open XML) is supported. Old `.ppt` files (binary format) must be converted to `.pptx` first. You can do this by opening the file in PowerPoint and using "Save As" to save as `.pptx` format.

## ⚠️ Important: Embedding Model Context Window Limits

**Embedding models have context window limitations** that restrict the maximum length of text they can process:

- **Ollama embedding models** (e.g., `nomic-embed-text`, `mxbai-embed-large`): Typically support 512-8192 tokens
- **OpenAI embedding models** (e.g., `text-embedding-3-small`): Support up to 8191 tokens

**Recommendations:**
- Set `chunk_size_tokens` in `config.yaml` to a value well below your model's limit (e.g., 256-512 for most Ollama models)
- If you encounter "context length exceeded" errors, reduce `chunk_size_tokens` further
- The system will automatically truncate or skip chunks that exceed the model's context window, but this may result in data loss

**Model-specific limits:**
- `nomic-embed-text`: ~512 tokens
- `mxbai-embed-large`: ~8192 tokens  
- `text-embedding-3-small` (OpenAI): 8191 tokens

Always verify your chunk sizes are appropriate for your chosen embedding model.

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `chromadb` - Vector database
- `pydantic` - Data validation
- `ollama` - Ollama client library
- `openai` - OpenAI client (optional, only if using OpenAI)
- `pypdf` - PDF parsing
- `python-pptx` - PPT/PPTX parsing
- `tiktoken` - Token counting
- `pyyaml` - YAML config parsing

### 2. Install Ollama

Ollama must be installed and running to generate embeddings (if using Ollama provider).

#### Windows
1. Download from [https://ollama.com/download](https://ollama.com/download)
2. Run the installer
3. Ollama will start automatically

#### macOS
```bash
# Using Homebrew
brew install ollama

# Or download from https://ollama.com/download
```

#### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify installation:
```bash
ollama --version
```

### 3. Download Embedding Model

After installing Ollama, download an embedding model:

```bash
# Recommended: nomic-embed-text (good balance of quality and speed)
ollama pull nomic-embed-text

# Alternative options:
# ollama pull mxbai-embed-large  # Larger, higher quality
# ollama pull all-minilm          # Smaller, faster
```

Verify the model is available:
```bash
ollama list
```

### 4. Start Ollama Service

Make sure Ollama is running:

```bash
# Start Ollama (usually runs automatically after installation)
ollama serve

# Or on Windows/macOS, it may run as a background service
# Check if it's running:
curl http://localhost:11434/api/tags
```

### 5. Configure the System

Edit `config.yaml` at the project root:

```yaml
embedding:
  provider: "ollama"  # or "openai"
  model: "nomic-embed-text"  # Must match the model you downloaded

ollama:
  base_url: "http://localhost:11434"  # Default Ollama URL

chromadb:
  db_path: "./chroma_db"
  collection_name: "documents"

chunking:
  chunk_size_tokens: 1000  # Max tokens per chunk
  overlap_sentences: 2  # Number of sentences to overlap (not used in hierarchical splitting)
```

## Usage

```python
from src.chunk_embed_store import ingest_document

# Ingest a PDF or PPT file (uses config.yaml)
num_chunks = ingest_document("path/to/document.pdf")
print(f"Created {num_chunks} chunks")
```

## Inputs/Outputs

### `ingest_document()`

**Inputs:**
- `file_path`: Path to PDF or PPT/PPTX file
- `config_path`: Path to config.yaml (default: "config.yaml")

**Outputs:**
- Returns number of chunks created

## Examples

```python
# Simple usage with default config.yaml
ingest_document("report.pdf")

# Use custom config file
ingest_document("presentation.pptx", config_path="custom_config.yaml")
```

## Chunking Details

The chunker uses hierarchical recursive splitting:

1. **Level 0**: Split by `\n\n` (paragraph breaks)
2. **Level 1**: Split by `\n` (line breaks)
3. **Level 2**: Split by sentence boundaries (`.`, `!`, `?`)
4. **Level 3**: Fallback to token-based soft splitting

Each chunk includes metadata:
- **PDF**: `page_num`, `source_unit: "page"`, `chunk_local_index`
- **PPT**: `slide_index`, `slide_title`, `source_unit: "slide"`, `chunk_local_index`

## Switching Embedding Providers

### Using Ollama (Default)

```yaml
embedding:
  provider: "ollama"
  model: "nomic-embed-text"  # Must be downloaded first
```

### Using OpenAI

1. Get an API key from [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

2. Edit `config.yaml`:
```yaml
embedding:
  provider: "openai"
  model: "text-embedding-3-small"
  api_key: "sk-..."  # or set OPENAI_API_KEY environment variable
```

Or set environment variable:
```bash
export OPENAI_API_KEY="sk-..."
```

## Troubleshooting

### PPT File Error: "File is not a zip file"
- **Cause**: You're trying to parse an old `.ppt` file (binary format)
- **Solution**: Only `.pptx` format is supported. Convert your file:
  1. Open the `.ppt` file in Microsoft PowerPoint (or LibreOffice)
  2. Go to File → Save As
  3. Choose `.pptx` format
  4. Save and use the new `.pptx` file

### Ollama Connection Error
- Ensure Ollama is running: `ollama serve`
- Check if model is downloaded: `ollama list`
- Verify base_url in config.yaml matches your Ollama instance

### Model Not Found
- Download the model: `ollama pull nomic-embed-text`
- Check model name in config.yaml matches downloaded model

### ChromaDB Errors
- Ensure write permissions for `db_path` directory
- Delete `chroma_db` folder and retry if corrupted

### Context Length Exceeded Error
- **Error**: "the input length exceeds the context length" or "context length exceeded"
- **Cause**: Chunks are too long for the embedding model's context window
- **Solutions**:
  1. Reduce `chunk_size_tokens` in `config.yaml` (try 256 or 512)
  2. Check your embedding model's context limit (see Important note above)
  3. The system will automatically skip chunks that are too long, but you may lose data
  4. Consider using a model with a larger context window if available
