"""Chunk and embed store module for PDF and PPT documents."""

from .pipeline import ingest_document
from .types import Chunk, Document, StoredChunk

__all__ = ["ingest_document", "Document", "Chunk", "StoredChunk"]
