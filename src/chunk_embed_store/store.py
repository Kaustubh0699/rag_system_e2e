"""Simple ChromaDB storage."""

import logging
from pathlib import Path
from typing import List

import chromadb
from chromadb.config import Settings

from .errors import StorageError
from .types import Chunk

logger = logging.getLogger(__name__)


def create_store(db_path: str = "./chroma_db", collection_name: str = "documents"):
    """Create ChromaDB client and collection."""
    try:
        # Convert to absolute path and ensure parent directory exists
        db_path = Path(db_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        collection = client.get_or_create_collection(name=collection_name)
        logger.info(f"Connected to ChromaDB at {db_path}")
        print(f"ChromaDB created at: {db_path}")
        return collection
    except Exception as e:
        logger.error(f"Failed to create store at {db_path}: {e}", exc_info=True)
        raise StorageError(f"Failed to create store: {e}") from e


def store_chunks(chunks: List[Chunk], embeddings: List[List[float]], collection):
    """Store chunks and embeddings in ChromaDB."""
    try:
        ids = [chunk.chunk_id for chunk in chunks]
        texts = [chunk.text for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(f"Stored {len(chunks)} chunks in ChromaDB")
    except Exception as e:
        raise StorageError(f"Failed to store chunks: {e}") from e
