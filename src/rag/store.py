"""ChromaDB vector store wrapper for documentation embeddings."""

import hashlib
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

import chromadb


@dataclass
class SearchResult:
    """Search result with content, metadata, and similarity score."""
    content: str
    source_url: str
    section: str
    score: float
    metadata: dict


class VectorStore:
    """ChromaDB-based vector store for documentation chunks."""

    # Default to absolute path in project directory
    DEFAULT_PERSIST_DIR = Path(__file__).parent.parent.parent / "data" / "chromadb"

    def __init__(self, collection_name: str = "gemini", persist_dir: str | Path | None = None):
        """
        Initialize ChromaDB with persistent storage.

        Args:
            collection_name: Name of the collection (e.g., "gemini", "openai")
            persist_dir: Directory for persistent storage (defaults to project's data/chromadb)
        """
        self.collection_name = collection_name
        self.persist_dir = Path(persist_dir) if persist_dir else self.DEFAULT_PERSIST_DIR

        # Create directory if it doesn't exist
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": f"Documentation embeddings for {collection_name}"}
        )

    def _generate_id(self, content: str, source_url: str) -> str:
        """Generate a unique ID for a chunk based on content and source."""
        combined = f"{source_url}:{content}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def add(self, chunks: list, embeddings: list[list[float]]) -> None:
        """
        Add chunks with their embeddings to the store.

        Args:
            chunks: List of Chunk objects with .content and .metadata attributes
            embeddings: Corresponding embedding vectors (same length as chunks)
        """
        if not chunks:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Number of chunks ({len(chunks)}) must match number of embeddings ({len(embeddings)})"
            )

        # Prepare data for ChromaDB (deduplicate by ID within batch)
        seen_ids = set()
        ids = []
        documents = []
        metadatas = []
        embeddings_list = []

        for chunk, embedding in zip(chunks, embeddings):
            # Generate unique ID
            chunk_id = self._generate_id(
                chunk.content,
                chunk.metadata.get("source_url", "")
            )

            # Skip duplicates within this batch
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)

            # ChromaDB only supports str, int, float, bool in metadata
            # Convert lists to strings (e.g., hierarchy list -> "Parent > Child")
            metadata = {}
            for key, value in chunk.metadata.items():
                if isinstance(value, list):
                    metadata[key] = " > ".join(str(v) for v in value) if value else ""
                else:
                    metadata[key] = value

            ids.append(chunk_id)
            documents.append(chunk.content)
            metadatas.append(metadata)
            embeddings_list.append(embedding)

        # Add to collection in batches (ChromaDB has a max batch size)
        batch_size = 5000  # Stay under ChromaDB's 5461 limit
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            self.collection.upsert(
                ids=ids[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
                embeddings=embeddings_list[i:end]
            )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        metadata_filter: Optional[dict] = None
    ) -> list[SearchResult]:
        """
        Search for similar chunks, return top_k results.

        Args:
            query_embedding: The query embedding vector
            top_k: Number of results to return
            metadata_filter: Optional metadata filter (e.g., {"source_url": "..."})

        Returns:
            List of SearchResult objects ordered by similarity
        """
        # Build query parameters
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": top_k
        }

        # Add metadata filter if provided
        if metadata_filter:
            query_params["where"] = metadata_filter

        # Query the collection
        results = self.collection.query(**query_params)

        # Convert to SearchResult objects
        search_results = []

        # ChromaDB returns lists of lists (one list per query)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, metadata, distance in zip(documents, metadatas, distances):
            # Convert distance to similarity score (ChromaDB uses L2 distance by default)
            # Smaller distance = more similar, so we invert it
            score = 1.0 / (1.0 + distance)

            search_results.append(SearchResult(
                content=doc,
                source_url=metadata.get("source_url", ""),
                section=metadata.get("section", ""),
                score=score,
                metadata=metadata
            ))

        return search_results

    def clear(self) -> None:
        """Clear all documents from the collection."""
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": f"Documentation embeddings for {self.collection_name}"}
        )

    def count(self) -> int:
        """Return number of documents in collection."""
        return self.collection.count()

    def get_all_documents(self) -> list[dict]:
        """Get all documents (for keyword search)."""
        results = self.collection.get()
        return [
            {"id": id, "content": doc, "metadata": meta}
            for id, doc, meta in zip(
                results.get("ids", []),
                results.get("documents", []),
                results.get("metadatas", [])
            )
        ]

    def get_by_source(self, source_url: str) -> list[dict]:
        """Get all chunks from a specific source URL."""
        results = self.collection.get(where={"source_url": source_url})
        return [
            {"content": doc, "metadata": meta}
            for doc, meta in zip(
                results.get("documents", []),
                results.get("metadatas", [])
            )
        ]

    def delete_by_source(self, source_url: str) -> None:
        """Delete all chunks from a specific source URL."""
        results = self.collection.get(where={"source_url": source_url})
        ids = results.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
