"""Hybrid search combining semantic and keyword search with RRF ranking."""

from dataclasses import dataclass
from typing import Optional
import re

from .embedder import Embedder
from .store import VectorStore, SearchResult


@dataclass
class HybridSearchResult:
    """Result from hybrid search with combined ranking."""
    content: str
    source_url: str
    section: str
    score: float  # Combined RRF score
    semantic_rank: Optional[int]
    keyword_rank: Optional[int]


class HybridSearch:
    """
    Hybrid search combining semantic and keyword search.

    Uses Reciprocal Rank Fusion (RRF) to combine results from:
    1. Semantic search via embeddings and vector similarity
    2. Keyword search via simple word matching
    """

    # RRF constant - prevents high ranks from dominating
    RRF_K = 60

    def __init__(self, collection_name: str = "gemini"):
        """
        Initialize with embedder and vector store.

        Args:
            collection_name: Name of the collection to search
        """
        self.collection_name = collection_name
        self.embedder = Embedder()
        self.vector_store = VectorStore(collection_name=collection_name)

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for keyword matching.

        Args:
            text: Text to normalize

        Returns:
            Normalized lowercase text
        """
        return text.lower().strip()

    def _extract_query_terms(self, query: str) -> list[str]:
        """
        Extract search terms from query.

        Args:
            query: Search query

        Returns:
            List of normalized query terms
        """
        # Normalize and split on whitespace
        normalized = self._normalize_text(query)

        # Split on whitespace and punctuation, keep words
        terms = re.findall(r'\b\w+\b', normalized)

        # Remove very short terms (single characters) and common stop words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with'
        }

        terms = [t for t in terms if len(t) > 1 and t not in stop_words]

        return terms

    def _keyword_score(self, text: str, query_terms: list[str]) -> float:
        """
        Score text by keyword matching.

        Counts how many query terms appear in the text.

        Args:
            text: Text to score
            query_terms: List of query terms to search for

        Returns:
            Score based on term frequency
        """
        if not query_terms:
            return 0.0

        normalized_text = self._normalize_text(text)

        # Count occurrences of each query term
        total_matches = 0
        for term in query_terms:
            # Count how many times this term appears
            total_matches += normalized_text.count(term)

        # Normalize by number of query terms to get a score
        # This gives higher scores to documents with more term occurrences
        return float(total_matches)

    def _semantic_search(
        self,
        query: str,
        top_k: int
    ) -> list[tuple[SearchResult, int]]:
        """
        Perform semantic search.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of (SearchResult, rank) tuples
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)

        # Search vector store
        results = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k
        )

        # Return with ranks (1-indexed)
        return [(result, rank + 1) for rank, result in enumerate(results)]

    def _keyword_search(
        self,
        query: str,
        top_k: int,
        candidate_pool: list[SearchResult]
    ) -> list[tuple[SearchResult, int]]:
        """
        Perform keyword search on candidate documents.

        Args:
            query: Search query
            top_k: Number of results to return
            candidate_pool: Pool of documents to search through

        Returns:
            List of (SearchResult, rank) tuples
        """
        # Extract query terms
        query_terms = self._extract_query_terms(query)

        if not query_terms:
            return []

        # Score all candidates
        scored_docs = []
        for doc in candidate_pool:
            # Score based on content and section title
            content_score = self._keyword_score(doc.content, query_terms)
            section_score = self._keyword_score(doc.section, query_terms) * 2.0  # Weight section higher

            total_score = content_score + section_score

            if total_score > 0:
                scored_docs.append((doc, total_score))

        # Sort by score descending
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # Take top_k and assign ranks
        top_docs = scored_docs[:top_k]

        return [(doc, rank + 1) for rank, (doc, _) in enumerate(top_docs)]

    def _get_candidate_pool(self, top_k: int) -> list[SearchResult]:
        """
        Get candidate documents for keyword search.

        For efficiency, we use semantic search to get a larger pool,
        then keyword search ranks within that pool.

        Args:
            top_k: Number of final results needed

        Returns:
            List of candidate documents
        """
        # Get 3x the requested results to ensure good coverage
        expanded_k = min(top_k * 3, 50)

        # Get all documents from collection
        # We'll use a dummy query to get diverse results
        # In practice, we want ALL documents for true keyword search,
        # but for efficiency we limit to expanded_k

        # Use the collection's get method to retrieve documents
        # Since VectorStore doesn't expose a get_all method,
        # we'll use a very generic embedding to get diverse results

        try:
            # Create a generic query embedding
            generic_embedding = self.embedder.embed_query("documentation")

            # Get expanded results
            results = self.vector_store.search(
                query_embedding=generic_embedding,
                top_k=expanded_k
            )

            return results
        except Exception:
            # If search fails, return empty list
            return []

    def _rrf_score(
        self,
        semantic_rank: Optional[int],
        keyword_rank: Optional[int]
    ) -> float:
        """
        Calculate Reciprocal Rank Fusion score.

        RRF formula: score = Σ 1 / (k + rank_i)

        Args:
            semantic_rank: Rank from semantic search (None if not found)
            keyword_rank: Rank from keyword search (None if not found)

        Returns:
            Combined RRF score
        """
        score = 0.0

        if semantic_rank is not None:
            score += 1.0 / (self.RRF_K + semantic_rank)

        if keyword_rank is not None:
            score += 1.0 / (self.RRF_K + keyword_rank)

        return score

    def _combine_results(
        self,
        semantic_results: list[tuple[SearchResult, int]],
        keyword_results: list[tuple[SearchResult, int]]
    ) -> dict[str, tuple[SearchResult, Optional[int], Optional[int]]]:
        """
        Combine semantic and keyword results.

        Args:
            semantic_results: List of (SearchResult, rank) from semantic search
            keyword_results: List of (SearchResult, rank) from keyword search

        Returns:
            Dictionary mapping document ID to (SearchResult, semantic_rank, keyword_rank)
        """
        combined = {}

        # Add semantic results
        for result, rank in semantic_results:
            # Use content hash as key for deduplication
            key = f"{result.source_url}:{hash(result.content)}"
            combined[key] = (result, rank, None)

        # Add/update with keyword results
        for result, rank in keyword_results:
            key = f"{result.source_url}:{hash(result.content)}"

            if key in combined:
                # Update existing entry with keyword rank
                existing_result, semantic_rank, _ = combined[key]
                combined[key] = (existing_result, semantic_rank, rank)
            else:
                # New entry from keyword search only
                combined[key] = (result, None, rank)

        return combined

    def search(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7,
    ) -> list[HybridSearchResult]:
        """
        Perform hybrid search combining semantic and keyword search.

        Args:
            query: Search query string
            top_k: Number of results to return
            semantic_weight: Weight for semantic search (0-1). Currently unused,
                           kept for API compatibility. RRF naturally balances results.

        Returns:
            List of HybridSearchResult ordered by RRF score

        Example:
            >>> searcher = HybridSearch("gemini")
            >>> results = searcher.search("how to use function calling", top_k=5)
            >>> for r in results:
            ...     print(f"[{r.score:.3f}] {r.section}")
        """
        if not query or not query.strip():
            return []

        # Perform semantic search
        semantic_results = self._semantic_search(query, top_k=top_k)

        # Get candidate pool for keyword search
        # Use semantic results + expanded pool for better coverage
        candidate_pool = [r for r, _ in semantic_results]

        # Add more candidates from expanded search
        expanded_pool = self._get_candidate_pool(top_k)

        # Combine pools and deduplicate
        seen = set()
        for doc in expanded_pool:
            key = f"{doc.source_url}:{hash(doc.content)}"
            if key not in seen:
                seen.add(key)
                if doc not in candidate_pool:
                    candidate_pool.append(doc)

        # Perform keyword search on candidate pool
        keyword_results = self._keyword_search(
            query,
            top_k=top_k,
            candidate_pool=candidate_pool
        )

        # Combine results
        combined = self._combine_results(semantic_results, keyword_results)

        # Calculate RRF scores and create HybridSearchResult objects
        hybrid_results = []
        for result, semantic_rank, keyword_rank in combined.values():
            rrf_score = self._rrf_score(semantic_rank, keyword_rank)

            hybrid_results.append(HybridSearchResult(
                content=result.content,
                source_url=result.source_url,
                section=result.section,
                score=rrf_score,
                semantic_rank=semantic_rank,
                keyword_rank=keyword_rank
            ))

        # Sort by RRF score descending
        hybrid_results.sort(key=lambda x: x.score, reverse=True)

        # Return top_k results
        return hybrid_results[:top_k]


def search(
    query: str,
    top_k: int = 5,
    collection: str = "gemini"
) -> list[HybridSearchResult]:
    """
    Convenience function for quick hybrid searches.

    Args:
        query: Search query string
        top_k: Number of results to return
        collection: Collection name to search (default: "gemini")

    Returns:
        List of HybridSearchResult ordered by combined score

    Example:
        >>> from src.rag.search import search
        >>> results = search("how to use function calling")
        >>> for r in results:
        ...     print(f"[{r.score:.3f}] {r.section}")
        ...     print(f"  Source: {r.source_url}")
        ...     print(f"  Ranks: semantic={r.semantic_rank}, keyword={r.keyword_rank}")
    """
    searcher = HybridSearch(collection_name=collection)
    return searcher.search(query, top_k=top_k)


if __name__ == "__main__":
    # Example usage
    print("Testing Hybrid Search...")

    try:
        # Create searcher
        searcher = HybridSearch("gemini")

        # Test query
        query = "how to use function calling"
        print(f"\nQuery: '{query}'")
        print("-" * 80)

        results = searcher.search(query, top_k=5)

        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r.score:.4f}] {r.section}")
            print(f"   Source: {r.source_url}")
            print(f"   Ranks: semantic={r.semantic_rank}, keyword={r.keyword_rank}")
            print(f"   Preview: {r.content[:200]}...")

        print("\n" + "=" * 80)
        print("Test completed successfully!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
