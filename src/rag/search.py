"""Hybrid search combining semantic and keyword search with RRF ranking."""

from dataclasses import dataclass
from typing import Optional

from .embedder import Embedder
from .sqlite_store import SQLiteStore, SearchResult
from .query_expander import QueryExpander

try:
    from .reranker import Reranker
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False


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

    Uses SQLite with FTS5 and sqlite-vec for efficient hybrid search
    with Reciprocal Rank Fusion (RRF) ranking.
    """

    def __init__(self, collection_name: str = "gemini"):
        """
        Initialize with embedder and SQLite store.

        Args:
            collection_name: Name of the collection to search
        """
        self.collection_name = collection_name
        self.embedder = Embedder()
        self.store = SQLiteStore(collection_name=collection_name)
        self.expander: Optional[QueryExpander] = None  # Lazy initialization
        self._reranker: Optional[Reranker] = None  # Lazy initialization

    def search(
        self,
        query: str,
        top_k: int = 5,
        semantic_weight: float = 0.7,
        rerank: bool = True,
        expand_query: bool = True,
    ) -> list[HybridSearchResult]:
        """
        Perform hybrid search combining semantic and keyword search.

        Args:
            query: Search query string
            top_k: Number of results to return
            semantic_weight: Weight for semantic search (0-1). Currently unused,
                           kept for API compatibility. RRF naturally balances results.
            rerank: If True, use cross-encoder reranking for improved relevance.
                   Retrieves top 50 candidates and reranks to top_k.
                   Requires sentence-transformers. Default: True.
            expand_query: If True, generate query variations for better recall.
                         Uses LLM to create alternative phrasings. Default: True.

        Returns:
            List of HybridSearchResult ordered by RRF score (or rerank score if enabled)

        Example:
            >>> searcher = HybridSearch("gemini")
            >>> results = searcher.search("how to use function calling", top_k=5)
            >>> for r in results:
            ...     print(f"[{r.score:.3f}] {r.section}")

            >>> # With reranking for better relevance
            >>> results = searcher.search("how to use function calling", top_k=5, rerank=True)

            >>> # With query expansion for better recall
            >>> results = searcher.search("how to use function calling", top_k=5, expand_query=True)

            >>> # Combine both for best results
            >>> results = searcher.search("how to use function calling", top_k=5, expand_query=True, rerank=True)
        """
        if not query or not query.strip():
            return []

        # Multi-query expansion if requested
        if expand_query:
            return self._search_with_expansion(query, top_k, rerank)

        # Standard single-query search
        # Determine retrieval size
        if rerank:
            if not RERANKER_AVAILABLE:
                import warnings
                warnings.warn(
                    "Reranking requested but sentence-transformers not available. "
                    "Install with: pip install sentence-transformers. "
                    "Falling back to standard search.",
                    RuntimeWarning
                )
                rerank = False
                retrieval_k = top_k
            else:
                # Retrieve more candidates for reranking
                retrieval_k = min(50, max(top_k * 10, 50))
        else:
            retrieval_k = top_k

        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)

        # Perform hybrid search in SQLite (handles RRF internally)
        results = self.store.search(
            query_embedding=query_embedding,
            query_text=query,
            top_k=retrieval_k
        )

        # Convert to HybridSearchResult
        hybrid_results = [
            HybridSearchResult(
                content=r.content,
                source_url=r.source_url,
                section=r.section,
                score=r.score,
                semantic_rank=r.semantic_rank,
                keyword_rank=r.keyword_rank
            )
            for r in results
        ]

        # Apply reranking if requested
        if rerank and hybrid_results:
            # Lazy initialize reranker
            if self._reranker is None:
                self._reranker = Reranker()

            # Rerank and update scores
            reranked = self._reranker.rerank(query, hybrid_results, top_k=top_k)

            # Update scores with rerank scores
            for rerank_result in reranked:
                rerank_result.original_result.score = rerank_result.rerank_score

            return [r.original_result for r in reranked]

        return hybrid_results

    def _search_with_expansion(self, query: str, top_k: int, rerank: bool = False) -> list[HybridSearchResult]:
        """
        Search with multi-query expansion using RRF fusion.

        Args:
            query: Original search query
            top_k: Number of final results to return
            rerank: If True, apply reranking after fusion

        Returns:
            List of HybridSearchResult ordered by combined RRF score
        """
        # Lazy initialize expander
        if self.expander is None:
            self.expander = QueryExpander()

        # Generate query variations
        queries = self.expander.expand(query)

        if len(queries) == 1:
            # Expansion failed or returned only original - fallback to normal search
            return self.search(query, top_k, expand_query=False, rerank=rerank)

        # Search with each query variation
        # Use larger pool for fusion (e.g., top_k * 3 per query)
        pool_size = max(top_k * 3, 20)
        all_results = []

        for i, q in enumerate(queries):
            # Generate embedding for this query
            q_embedding = self.embedder.embed_query(q)

            # Search with this query
            q_results = self.store.search(
                query_embedding=q_embedding,
                query_text=q,
                top_k=pool_size
            )

            # Tag results with query index for debugging
            for r in q_results:
                all_results.append((i, r))

        # Fusion with RRF across all query results
        doc_scores = {}  # doc_id -> {'data': ..., 'rrf_contributions': []}

        for query_idx, result in all_results:
            doc_id = self.store._generate_id(result.content, result.source_url)

            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    'content': result.content,
                    'source_url': result.source_url,
                    'section': result.section,
                    'rrf_contributions': []
                }

            # Add RRF contribution from this query result
            # Use the already computed RRF score from individual query
            doc_scores[doc_id]['rrf_contributions'].append(result.score)

        # Combine RRF scores across queries
        final_results = []
        for doc_id, data in doc_scores.items():
            # Sum RRF contributions from all queries
            combined_score = sum(data['rrf_contributions'])

            final_results.append(HybridSearchResult(
                content=data['content'],
                source_url=data['source_url'],
                section=data['section'],
                score=combined_score,
                semantic_rank=None,  # Multi-query doesn't have single rank
                keyword_rank=None
            ))

        # Sort by combined score
        final_results.sort(key=lambda x: x.score, reverse=True)

        # Apply reranking if requested
        if rerank and final_results:
            if not RERANKER_AVAILABLE:
                import warnings
                warnings.warn(
                    "Reranking requested but sentence-transformers not available. "
                    "Install with: pip install sentence-transformers. "
                    "Skipping reranking.",
                    RuntimeWarning
                )
            else:
                # Lazy initialize reranker
                if self._reranker is None:
                    self._reranker = Reranker()

                # Take larger pool for reranking
                rerank_pool = min(50, len(final_results))
                rerank_candidates = final_results[:rerank_pool]

                # Rerank
                reranked = self._reranker.rerank(query, rerank_candidates, top_k=top_k)

                # Update scores with rerank scores
                for rerank_result in reranked:
                    rerank_result.original_result.score = rerank_result.rerank_score

                return [r.original_result for r in reranked]

        return final_results[:top_k]


def search(
    query: str,
    top_k: int = 5,
    collection: str = "gemini",
    rerank: bool = True,
    expand_query: bool = True
) -> list[HybridSearchResult]:
    """
    Convenience function for quick hybrid searches.

    Args:
        query: Search query string
        top_k: Number of results to return
        collection: Collection name to search (default: "gemini")
        rerank: If True, use cross-encoder reranking (default: True)
        expand_query: If True, use multi-query expansion (default: True)

    Returns:
        List of HybridSearchResult ordered by combined score

    Example:
        >>> from src.rag.search import search
        >>> results = search("how to use function calling")
        >>> for r in results:
        ...     print(f"[{r.score:.3f}] {r.section}")
        ...     print(f"  Source: {r.source_url}")
        ...     print(f"  Ranks: semantic={r.semantic_rank}, keyword={r.keyword_rank}")

        >>> # With reranking
        >>> results = search("how to use function calling", rerank=True)

        >>> # With query expansion
        >>> results = search("how to use function calling", expand_query=True)

        >>> # Combine both
        >>> results = search("how to use function calling", expand_query=True, rerank=True)
    """
    searcher = HybridSearch(collection_name=collection)
    return searcher.search(query, top_k=top_k, rerank=rerank, expand_query=expand_query)


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
