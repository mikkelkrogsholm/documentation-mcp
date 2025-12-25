"""RAG (Retrieval Augmented Generation) utilities."""

from .chunker import Chunk, chunk_markdown

__all__ = ["Chunk", "chunk_markdown"]

# Conditional imports for optional dependencies
try:
    from .sqlite_store import SQLiteStore, SearchResult
    __all__.extend(["SQLiteStore", "SearchResult"])
except (ImportError, ModuleNotFoundError):
    # sqlite-vec not installed
    pass

try:
    from .embedder import Embedder
    __all__.append("Embedder")
except (ImportError, ModuleNotFoundError, SystemExit):
    # Embedder dependencies not installed or embedder raised SystemExit
    pass
