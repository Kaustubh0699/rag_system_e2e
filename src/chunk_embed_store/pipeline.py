"""Simple pipeline to ingest, chunk, and store documents."""

import logging
from pathlib import Path
import json
from .chunker import chunk_document, parse_document
from .config_loader import load_config
from .embedder import embed_chunks
from .store import create_store, store_chunks

logger = logging.getLogger(__name__)


def ingest_document(
    file_path: str | Path,
    config_path: str | Path = "config.yaml",
):
    """Ingest a PDF or PPT file: parse, chunk, embed, and store in ChromaDB."""
    file_path = Path(file_path)
    
    # Load config
    config = load_config(config_path)
    
    logger.info(f"Starting ingestion of {file_path}")
    
    # Parse document
    document = parse_document(file_path)
    logger.info(f"Parsed document: {document.doc_id}")

    # # Validating parsing output for both PPT an PDF
    # with open("file.txt", "w", encoding="utf-8") as f:
    #     f.write(document.text)
    
    # Chunk document (hierarchical recursive: paragraphs -> lines -> sentences -> tokens)
    chunking_config = config.get("chunking", {})
    chunk_size_tokens = chunking_config.get("chunk_size_tokens", 1000)
    overlap_sentences = chunking_config.get("overlap_sentences", 2)  # Not used in hierarchical splitting
    
    chunks = chunk_document(document, chunk_size_tokens, overlap_sentences)
    logger.info(f"Created {len(chunks)} chunks")

    # # Validating chunking output in json format with parsing output for both PPT an PDF
    # try:
    #     chunks_dict = [chunk.model_dump() for chunk in chunks]
    #     json_path = Path("file.json").resolve()
    #     with open(json_path, "w", encoding="utf-8") as f:
    #         json.dump(chunks_dict, f, indent=2, ensure_ascii=False)
    #     logger.info(f"Saved {len(chunks_dict)} chunks to {json_path}")
    # except Exception as e:
    #     logger.error(f"Failed to write file.json: {e}", exc_info=True)
    #     raise

    # Generate embeddings
    embeddings = embed_chunks(chunks, config)
    
    # Store in ChromaDB
    chromadb_config = config.get("chromadb", {})
    db_path = chromadb_config.get("db_path", "./chroma_db")
    collection_name = chromadb_config.get("collection_name", "documents")
    
    logger.info(f"Creating ChromaDB store at: {db_path}")
    print(f"Creating ChromaDB store at: {db_path}")
    collection = create_store(db_path, collection_name)
    store_chunks(chunks, embeddings, collection)
    
    logger.info(f"Successfully ingested {file_path}")
    print(f"Successfully ingested {file_path}")
    return len(chunks)
