"""Simple error classes."""


class ChunkEmbedStoreError(Exception):
    """Base exception for chunk_embed_store module."""
    pass


class DocumentParseError(ChunkEmbedStoreError):
    """Raised when document parsing fails."""
    pass


class UnsupportedFileFormatError(ChunkEmbedStoreError):
    """Raised when an unsupported file format is provided."""
    pass


class EmbeddingError(ChunkEmbedStoreError):
    """Raised when embedding generation fails."""
    pass


class StorageError(ChunkEmbedStoreError):
    """Raised when storage operations fail."""
    pass
