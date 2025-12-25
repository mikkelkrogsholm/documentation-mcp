"""SQLite vector store with FTS5 and sqlite-vec for hybrid search."""

import hashlib
import json
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import sqlite_vec


@dataclass
class SearchResult:
    """Search result with content, metadata, and similarity score."""
    content: str
    source_url: str
    section: str
    score: float
    metadata: dict
    semantic_rank: Optional[int] = None
    keyword_rank: Optional[int] = None


class SQLiteStore:
    """SQLite-based vector store with FTS5 and sqlite-vec for hybrid search."""

    DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "docs.db"
    EMBEDDING_DIM = 1024  # bge-m3 dimension

    # Hybrid search tuning parameters
    RRF_K = 60  # Reciprocal Rank Fusion constant (higher = more equal weighting)
    SEMANTIC_WEIGHT = 1.0  # Weight for semantic search in RRF
    KEYWORD_WEIGHT = 1.2  # Weight for keyword search (slightly boosted for exact matches)
    SECTION_BOOST = 2.0  # Boost for matches in section titles
    MIN_POOL_SIZE = 100  # Minimum candidate pool for RRF fusion
    MAX_POOL_SIZE = 200  # Maximum candidate pool

    # Stop words to filter from FTS queries
    STOP_WORDS = frozenset({
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that',
        'the', 'to', 'was', 'were', 'will', 'with', 'how', 'what', 'when',
        'where', 'which', 'who', 'why', 'can', 'do', 'does', 'should', 'would'
    })

    def __init__(self, collection_name: str = "gemini", db_path: Path | None = None):
        """
        Initialize SQLite store with FTS5 and sqlite-vec.

        Args:
            collection_name: Name of the collection (used for filtering)
            db_path: Path to SQLite database file
        """
        self.collection_name = collection_name
        self.db_path = db_path or self.DEFAULT_DB_PATH

        # Create directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with sqlite-vec loaded."""
        conn = sqlite3.connect(str(self.db_path))
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            # Main documents table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    collection TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_url TEXT,
                    section TEXT,
                    metadata TEXT,
                    embedding BLOB
                )
            """)

            # Indexes for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_collection
                ON documents(collection)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_source
                ON documents(source_url)
            """)

            # FTS5 virtual table for keyword search
            # Check if FTS table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='documents_fts'
            """)
            if not cursor.fetchone():
                conn.execute("""
                    CREATE VIRTUAL TABLE documents_fts USING fts5(
                        content,
                        section,
                        content='documents',
                        content_rowid='rowid'
                    )
                """)

                # Triggers to keep FTS in sync
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                        INSERT INTO documents_fts(rowid, content, section)
                        VALUES (new.rowid, new.content, new.section);
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                        INSERT INTO documents_fts(documents_fts, rowid, content, section)
                        VALUES ('delete', old.rowid, old.content, old.section);
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                        INSERT INTO documents_fts(documents_fts, rowid, content, section)
                        VALUES ('delete', old.rowid, old.content, old.section);
                        INSERT INTO documents_fts(rowid, content, section)
                        VALUES (new.rowid, new.content, new.section);
                    END
                """)

            # sqlite-vec virtual table for vector search
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='documents_vec'
            """)
            if not cursor.fetchone():
                conn.execute(f"""
                    CREATE VIRTUAL TABLE documents_vec USING vec0(
                        embedding float[{self.EMBEDDING_DIM}]
                    )
                """)

            conn.commit()
        finally:
            conn.close()

    def _generate_id(self, content: str, source_url: str) -> str:
        """Generate a unique ID for a chunk based on content and source."""
        combined = f"{source_url}:{content}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _serialize_embedding(self, embedding: list[float]) -> bytes:
        """Serialize embedding to bytes for sqlite-vec."""
        return struct.pack(f"{len(embedding)}f", *embedding)

    def _deserialize_embedding(self, data: bytes) -> list[float]:
        """Deserialize embedding from bytes."""
        count = len(data) // 4
        return list(struct.unpack(f"{count}f", data))

    def add(self, chunks: list, embeddings: list[list[float]]) -> None:
        """
        Add chunks with their embeddings to the store.

        Args:
            chunks: List of Chunk objects with .content and .metadata attributes
            embeddings: Corresponding embedding vectors
        """
        if not chunks:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Number of chunks ({len(chunks)}) must match embeddings ({len(embeddings)})"
            )

        conn = self._get_connection()
        try:
            # Deduplicate within batch
            seen_ids = set()

            for chunk, embedding in zip(chunks, embeddings):
                chunk_id = self._generate_id(
                    chunk.content,
                    chunk.metadata.get("source_url", "")
                )

                if chunk_id in seen_ids:
                    continue
                seen_ids.add(chunk_id)

                # Prepare metadata (convert lists to strings)
                metadata = {}
                for key, value in chunk.metadata.items():
                    if isinstance(value, list):
                        metadata[key] = " > ".join(str(v) for v in value) if value else ""
                    else:
                        metadata[key] = value

                # Serialize embedding
                embedding_bytes = self._serialize_embedding(embedding)

                # Check if document exists
                cursor = conn.execute(
                    "SELECT rowid FROM documents WHERE id = ?",
                    (chunk_id,)
                )
                existing = cursor.fetchone()

                if existing:
                    # Update existing document
                    rowid = existing[0]
                    conn.execute("""
                        UPDATE documents
                        SET content = ?, source_url = ?, section = ?,
                            metadata = ?, embedding = ?
                        WHERE id = ?
                    """, (
                        chunk.content,
                        metadata.get("source_url", ""),
                        metadata.get("section", ""),
                        json.dumps(metadata),
                        embedding_bytes,
                        chunk_id
                    ))
                    # Update vector table
                    conn.execute(
                        "UPDATE documents_vec SET embedding = ? WHERE rowid = ?",
                        (embedding_bytes, rowid)
                    )
                else:
                    # Insert new document
                    cursor = conn.execute("""
                        INSERT INTO documents (id, collection, content, source_url, section, metadata, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        chunk_id,
                        self.collection_name,
                        chunk.content,
                        metadata.get("source_url", ""),
                        metadata.get("section", ""),
                        json.dumps(metadata),
                        embedding_bytes
                    ))
                    rowid = cursor.lastrowid
                    # Insert into vector table
                    conn.execute(
                        "INSERT INTO documents_vec (rowid, embedding) VALUES (?, ?)",
                        (rowid, embedding_bytes)
                    )

            conn.commit()
        finally:
            conn.close()

    def _parse_fts_query(self, query_text: str) -> str:
        """
        Parse query text into optimized FTS5 query.

        Handles:
        - Stop word removal
        - Phrase detection (quoted strings)
        - Boolean operators
        - Prefix matching for partial words
        """
        import re

        query_text = query_text.strip()
        if not query_text:
            return ""

        # Extract quoted phrases first
        phrases = re.findall(r'"([^"]+)"', query_text)
        # Remove quoted phrases from query
        remaining = re.sub(r'"[^"]+"', '', query_text)

        # Extract individual terms
        terms = []
        for word in remaining.split():
            # Clean punctuation
            word = re.sub(r'[^\w\-]', '', word.lower())
            if len(word) > 1 and word not in self.STOP_WORDS:
                terms.append(word)

        # Build FTS query parts
        parts = []

        # Add phrases with high priority
        for phrase in phrases:
            clean_phrase = ' '.join(
                w for w in phrase.split()
                if w.lower() not in self.STOP_WORDS
            )
            if clean_phrase:
                parts.append(f'"{clean_phrase}"')

        # Add individual terms with prefix matching for flexibility
        for term in terms:
            # Use prefix matching (*) for terms >= 3 chars for flexibility
            if len(term) >= 3:
                parts.append(f'"{term}"*')
            else:
                parts.append(f'"{term}"')

        if not parts:
            return ""

        # Combine with OR (any match) - FTS5 will use BM25 to rank
        return " OR ".join(parts)

    def search(
        self,
        query_embedding: list[float],
        query_text: str = "",
        top_k: int = 5,
        semantic_only: bool = False
    ) -> list[SearchResult]:
        """
        Hybrid search combining semantic and keyword search with weighted RRF.

        Uses:
        - sqlite-vec for semantic similarity (vector search)
        - FTS5 with BM25 for keyword relevance
        - Weighted Reciprocal Rank Fusion to combine results
        - Section title boosting for better relevance

        Args:
            query_embedding: Query embedding vector
            query_text: Original query text for keyword search
            top_k: Number of results to return
            semantic_only: If True, skip keyword search

        Returns:
            List of SearchResult objects ordered by combined RRF score
        """
        conn = self._get_connection()
        try:
            query_bytes = self._serialize_embedding(query_embedding)

            # Larger pool for better recall in RRF fusion
            pool_size = max(self.MIN_POOL_SIZE, min(top_k * 10, self.MAX_POOL_SIZE))

            # Semantic search using sqlite-vec
            semantic_results = conn.execute("""
                SELECT
                    d.rowid,
                    d.id,
                    d.content,
                    d.source_url,
                    d.section,
                    d.metadata,
                    v.distance
                FROM documents_vec v
                JOIN documents d ON d.rowid = v.rowid
                WHERE v.embedding MATCH ?
                  AND k = ?
                  AND d.collection = ?
                ORDER BY v.distance
            """, (query_bytes, pool_size, self.collection_name)).fetchall()

            if semantic_only or not query_text.strip():
                # Return semantic results only with weighted scores
                results = []
                for rank, row in enumerate(semantic_results[:top_k], 1):
                    score = self.SEMANTIC_WEIGHT / (self.RRF_K + rank)
                    metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                    results.append(SearchResult(
                        content=row["content"],
                        source_url=row["source_url"] or "",
                        section=row["section"] or "",
                        score=score,
                        metadata=metadata,
                        semantic_rank=rank,
                        keyword_rank=None
                    ))
                return results

            # Parse and optimize FTS query
            fts_query = self._parse_fts_query(query_text)

            # Keyword search using FTS5 with BM25 ranking
            keyword_results = []
            section_matches = set()  # Track docs with section title matches

            if fts_query:
                # Search content
                keyword_results = conn.execute("""
                    SELECT
                        d.rowid,
                        d.id,
                        d.content,
                        d.source_url,
                        d.section,
                        d.metadata,
                        bm25(documents_fts) as bm25_score
                    FROM documents_fts fts
                    JOIN documents d ON d.rowid = fts.rowid
                    WHERE d.collection = ?
                      AND documents_fts MATCH ?
                    ORDER BY bm25_score
                    LIMIT ?
                """, (self.collection_name, fts_query, pool_size)).fetchall()

                # Check for section title matches (for boosting)
                query_terms = set(
                    w.lower() for w in query_text.split()
                    if len(w) > 1 and w.lower() not in self.STOP_WORDS
                )
                for row in keyword_results:
                    section_lower = (row["section"] or "").lower()
                    if any(term in section_lower for term in query_terms):
                        section_matches.add(row["id"])

            # Build RRF ranking with weighted scores
            doc_scores = {}

            # Add semantic results
            for rank, row in enumerate(semantic_results, 1):
                doc_id = row["id"]
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                doc_scores[doc_id] = {
                    "content": row["content"],
                    "source_url": row["source_url"] or "",
                    "section": row["section"] or "",
                    "metadata": metadata,
                    "semantic_rank": rank,
                    "keyword_rank": None,
                    "section_match": False
                }

            # Add/update keyword results
            for rank, row in enumerate(keyword_results, 1):
                doc_id = row["id"]
                is_section_match = doc_id in section_matches

                if doc_id in doc_scores:
                    doc_scores[doc_id]["keyword_rank"] = rank
                    doc_scores[doc_id]["section_match"] = is_section_match
                else:
                    metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                    doc_scores[doc_id] = {
                        "content": row["content"],
                        "source_url": row["source_url"] or "",
                        "section": row["section"] or "",
                        "metadata": metadata,
                        "semantic_rank": None,
                        "keyword_rank": rank,
                        "section_match": is_section_match
                    }

            # Calculate weighted RRF scores
            results = []
            for doc_id, data in doc_scores.items():
                rrf_score = 0.0

                # Semantic contribution
                if data["semantic_rank"]:
                    rrf_score += self.SEMANTIC_WEIGHT / (self.RRF_K + data["semantic_rank"])

                # Keyword contribution with optional section boost
                if data["keyword_rank"]:
                    keyword_contribution = self.KEYWORD_WEIGHT / (self.RRF_K + data["keyword_rank"])
                    if data["section_match"]:
                        keyword_contribution *= self.SECTION_BOOST
                    rrf_score += keyword_contribution

                results.append(SearchResult(
                    content=data["content"],
                    source_url=data["source_url"],
                    section=data["section"],
                    score=rrf_score,
                    metadata=data["metadata"],
                    semantic_rank=data["semantic_rank"],
                    keyword_rank=data["keyword_rank"]
                ))

            # Sort by RRF score and return top_k
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:top_k]

        finally:
            conn.close()

    def clear(self) -> None:
        """Clear all documents from this collection."""
        conn = self._get_connection()
        try:
            # Get rowids for this collection
            rows = conn.execute(
                "SELECT rowid FROM documents WHERE collection = ?",
                (self.collection_name,)
            ).fetchall()
            rowids = [r[0] for r in rows]

            if rowids:
                # Delete from vector table
                placeholders = ",".join("?" * len(rowids))
                conn.execute(
                    f"DELETE FROM documents_vec WHERE rowid IN ({placeholders})",
                    rowids
                )
                # Delete from main table (triggers handle FTS)
                conn.execute(
                    "DELETE FROM documents WHERE collection = ?",
                    (self.collection_name,)
                )
                conn.commit()
        finally:
            conn.close()

    def count(self) -> int:
        """Return number of documents in this collection."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE collection = ?",
                (self.collection_name,)
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def get_all_documents(self) -> list[dict]:
        """Get all documents in this collection (for keyword search fallback)."""
        conn = self._get_connection()
        try:
            rows = conn.execute("""
                SELECT id, content, metadata
                FROM documents
                WHERE collection = ?
            """, (self.collection_name,)).fetchall()

            return [
                {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_by_source(self, source_url: str) -> list[dict]:
        """Get all chunks from a specific source URL."""
        conn = self._get_connection()
        try:
            rows = conn.execute("""
                SELECT content, metadata
                FROM documents
                WHERE collection = ? AND source_url = ?
            """, (self.collection_name, source_url)).fetchall()

            return [
                {
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }
                for row in rows
            ]
        finally:
            conn.close()

    def delete_by_source(self, source_url: str) -> None:
        """Delete all chunks from a specific source URL."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT rowid FROM documents WHERE collection = ? AND source_url = ?",
                (self.collection_name, source_url)
            ).fetchall()
            rowids = [r[0] for r in rows]

            if rowids:
                placeholders = ",".join("?" * len(rowids))
                conn.execute(
                    f"DELETE FROM documents_vec WHERE rowid IN ({placeholders})",
                    rowids
                )
                conn.execute(
                    "DELETE FROM documents WHERE collection = ? AND source_url = ?",
                    (self.collection_name, source_url)
                )
                conn.commit()
        finally:
            conn.close()

    @classmethod
    def list_collections(cls, db_path: Path | None = None) -> list[str]:
        """List all collections in the database."""
        path = db_path or cls.DEFAULT_DB_PATH
        if not path.exists():
            return []

        conn = sqlite3.connect(str(path))
        try:
            cursor = conn.execute("""
                SELECT DISTINCT collection FROM documents
            """)
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    @classmethod
    def collection_count(cls, collection: str, db_path: Path | None = None) -> int:
        """Get document count for a specific collection."""
        path = db_path or cls.DEFAULT_DB_PATH
        if not path.exists():
            return 0

        store = cls(collection_name=collection, db_path=path)
        return store.count()
