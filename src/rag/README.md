# RAG Module

Retrieval Augmented Generation utilities for documentation search.

## Components

### Chunker (`chunker.py`)
Intelligently splits markdown documentation into semantic chunks while preserving structure and extracting metadata.

### SQLite Store (`sqlite_store.py`)
SQLite-based vector store using FTS5 for keyword search and sqlite-vec for semantic search, with RRF fusion.

### Search (`search.py`)
Hybrid search combining semantic and keyword search with:
- Multi-query expansion (LLM-generated query variations)
- Cross-encoder reranking for improved relevance

## Installation

```bash
pip install -r requirements.txt
```

This will install sqlite-vec, sentence-transformers, and other dependencies.

## Usage

### 1. Chunk markdown files

```python
from pathlib import Path
from src.rag import chunk_markdown

chunks = chunk_markdown(Path("output/gemini/function-calling.md"))

for chunk in chunks:
    print(f"Section: {chunk.metadata['section']}")
    print(f"Content: {chunk.content[:100]}...")
```

### 2. Store chunks with embeddings

```python
from src.rag import SQLiteStore
from src.rag.embedder import Embedder

# Initialize store and embedder
store = SQLiteStore(collection_name="gemini")
embedder = Embedder()

# Generate embeddings
embeddings = embedder.embed([chunk.content for chunk in chunks])

# Add to store
store.add(chunks, embeddings)

print(f"Total documents: {store.count()}")
```

### 3. Search for similar content

```python
from src.rag.search import search

# Search with hybrid search + reranking + query expansion (all enabled by default)
results = search("How do I make API calls?", collection="gemini", top_k=5)

for result in results:
    print(f"Score: {result.score:.4f}")
    print(f"Source: {result.source_url}")
    print(f"Section: {result.section}")
    print(f"Content: {result.content[:200]}...")
    print()
```

### 4. Disable advanced features for speed

```python
# Disable query expansion and reranking for faster (but less accurate) search
results = search("query", collection="gemini", expand_query=False, rerank=False)
```

## Data Persistence

SQLite stores data in `data/docs.db`. Each documentation source gets its own collection within the database.

## Chunk Metadata

Each chunk includes rich metadata:
- `source_url`: Original documentation URL
- `page_title`: Page title from H1 header
- `section`: Section name from H2/H3 headers
- `hierarchy`: Full section hierarchy (breadcrumbs)
- `has_code`: Boolean indicating if chunk contains code blocks

This metadata can be used for filtering and improving search relevance.
