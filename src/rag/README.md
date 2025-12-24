# RAG Module

Retrieval Augmented Generation utilities for documentation search.

## Components

### Chunker (`chunker.py`)
Intelligently splits markdown documentation into semantic chunks while preserving structure and extracting metadata.

### Vector Store (`store.py`)
ChromaDB-based vector store for storing and searching documentation embeddings.

## Installation

```bash
pip install -r requirements.txt
```

This will install ChromaDB and other dependencies.

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
from src.rag import VectorStore

# Initialize store
store = VectorStore(collection_name="gemini", persist_dir="data/chromadb")

# Generate embeddings (use your preferred embedding model)
embeddings = [embed_model.encode(chunk.content) for chunk in chunks]

# Add to store
store.add(chunks, embeddings)

print(f"Total documents: {store.count()}")
```

### 3. Search for similar content

```python
# Generate query embedding
query = "How do I make API calls?"
query_embedding = embed_model.encode(query)

# Search
results = store.search(query_embedding, top_k=5)

for result in results:
    print(f"Score: {result.score:.4f}")
    print(f"Source: {result.source_url}")
    print(f"Section: {result.section}")
    print(f"Content: {result.content[:200]}...")
    print()
```

### 4. Search with metadata filtering

```python
# Search only within specific source
results = store.search(
    query_embedding,
    top_k=5,
    metadata_filter={"source_url": "https://ai.google.dev/gemini-api/docs/function-calling"}
)
```

### 5. Manage collections

```python
# Get all chunks from a source
chunks = store.get_by_source("https://ai.google.dev/gemini-api/docs/...")

# Delete chunks from a source
store.delete_by_source("https://ai.google.dev/gemini-api/docs/...")

# Clear entire collection
store.clear()

# Check count
count = store.count()
```

## Embedding Models

The VectorStore works with any embedding model. Popular choices:

### OpenAI Embeddings
```python
from openai import OpenAI

client = OpenAI()

def get_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
```

### Sentence Transformers
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

def get_embedding(text: str) -> list[float]:
    return model.encode(text).tolist()
```

### Gemini Embeddings
```python
import google.generativeai as genai

genai.configure(api_key="YOUR_API_KEY")

def get_embedding(text: str) -> list[float]:
    result = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="retrieval_document"
    )
    return result['embedding']
```

## Data Persistence

ChromaDB stores data persistently in `data/chromadb/` by default. Each documentation source gets its own collection (e.g., "gemini", "openai", "anthropic").

## Chunk Metadata

Each chunk includes rich metadata:
- `source_url`: Original documentation URL
- `page_title`: Page title from H1 header
- `section`: Section name from H2/H3 headers
- `hierarchy`: Full section hierarchy (breadcrumbs) - stored as string with " > " separator
- `has_code`: Boolean indicating if chunk contains code blocks

This metadata can be used for filtering and improving search relevance.

**Note:** ChromaDB only supports str, int, float, and bool metadata values. The VectorStore automatically converts lists (like `hierarchy`) to strings using " > " as a separator (e.g., `["Getting Started", "Installation"]` becomes `"Getting Started > Installation"`).

## Example

See `example_store_usage.py` in the project root for a complete working example.
