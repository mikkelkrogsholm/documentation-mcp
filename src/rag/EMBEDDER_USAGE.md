# Ollama Embedder Usage Guide

The `Embedder` class provides a simple interface to generate text embeddings using a local Ollama instance.

## Prerequisites

1. **Install Ollama**: Download from [ollama.com](https://ollama.com)
2. **Pull the embedding model**:
   ```bash
   ollama pull bge-m3
   ```
3. **Install Python dependencies**:
   ```bash
   pip install ollama
   ```

## Basic Usage

### Initialize the Embedder

```python
from src.rag.embedder import Embedder

# Use default model (bge-m3) and host (http://localhost:11434)
embedder = Embedder()

# Or specify custom model and host
embedder = Embedder(model="nomic-embed-text", host="http://localhost:11434")
```

### Embed a Single Query

```python
# Embed a single text query
query = "What is machine learning?"
vector = embedder.embed_query(query)

print(f"Vector dimensions: {len(vector)}")
print(f"First 5 values: {vector[:5]}")
```

### Embed Multiple Texts (Batch)

```python
# Embed multiple texts efficiently
texts = [
    "The sky is blue because of Rayleigh scattering",
    "Grass is green because of chlorophyll",
    "The ocean appears blue due to water absorption"
]

vectors = embedder.embed(texts)

print(f"Generated {len(vectors)} embedding vectors")
for i, vec in enumerate(vectors):
    print(f"Text {i+1}: {len(vec)} dimensions")
```

### Get Model Information

```python
# Get information about the current model
info = embedder.get_model_info()

print(f"Model: {info['model']}")
print(f"Host: {info['host']}")
print(f"Dimensions: {info['dimensions']}")
```

## Error Handling

The embedder provides helpful error messages for common issues:

### Ollama Not Running

```python
try:
    embedder = Embedder()
except ConnectionError as e:
    print(f"Connection error: {e}")
    # Output will suggest checking if Ollama is running
```

### Model Not Available

```python
try:
    embedder = Embedder(model="nonexistent-model")
    # Will show warning but allow initialization
    
    # Error occurs when trying to embed
    vector = embedder.embed_query("test")
except RuntimeError as e:
    print(f"Runtime error: {e}")
    # Output will suggest: ollama pull nonexistent-model
```

## Integration with Vector Stores

Use with ChromaDB or other vector databases:

```python
from src.rag.embedder import Embedder
from src.rag.store import VectorStore

# Initialize embedder and vector store
embedder = Embedder()
store = VectorStore(collection_name="my_docs")

# Prepare documents
documents = [
    "Document 1 content here",
    "Document 2 content here",
    "Document 3 content here"
]

# Generate embeddings
embeddings = embedder.embed(documents)

# Store in vector database
for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
    store.add_document(
        doc_id=f"doc_{i}",
        content=doc,
        embedding=embedding
    )

# Query using embeddings
query = "search query"
query_embedding = embedder.embed_query(query)
results = store.search(query_embedding, top_k=5)
```

## Running the Test Suite

The embedder includes a built-in test that you can run:

```bash
python -m src.rag.embedder
```

This will:
1. Connect to Ollama
2. Display model information
3. Test single query embedding
4. Test batch embedding
5. Display results

## Supported Models

Common embedding models you can use with Ollama:

- `bge-m3`: Default, good general-purpose model (1024 dimensions)
- `nomic-embed-text`: Fast and efficient (768 dimensions)
- `mxbai-embed-large`: High quality embeddings (1024 dimensions)
- `all-minilm`: Lightweight and fast (384 dimensions)

Pull any model with:
```bash
ollama pull <model-name>
```

## Performance Tips

1. **Use batch embedding**: Always prefer `embed()` over multiple `embed_query()` calls
2. **Connection pooling**: Reuse the same `Embedder` instance
3. **Model selection**: Choose smaller models for speed, larger for accuracy
4. **Local hosting**: Run Ollama locally to avoid network latency

## Troubleshooting

### "Connection refused" error
- Make sure Ollama is running: `ollama serve`
- Check the host URL is correct
- Verify firewall isn't blocking port 11434

### "Model not found" error
- Pull the model: `ollama pull bge-m3`
- List available models: `ollama list`
- Check model name spelling

### Slow embedding speed
- Use a smaller model (e.g., `all-minilm`)
- Enable GPU acceleration if available
- Increase batch size for bulk operations

## API Reference

### `Embedder.__init__(model, host)`
Initialize the embedder with specified model and host.

### `Embedder.embed(texts: list[str]) -> list[list[float]]`
Generate embeddings for multiple texts in batch.

### `Embedder.embed_query(query: str) -> list[float]`
Generate embedding for a single query string.

### `Embedder.get_model_info() -> dict`
Get information about the current model configuration.
