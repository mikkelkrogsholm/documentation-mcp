"""Cross-encoder reranker for improving search result relevance."""

from dataclasses import dataclass
from typing import Protocol

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None


class SearchResultProtocol(Protocol):
    """Protocol for search result objects with content and score."""
    content: str
    score: float


@dataclass
class RerankResult:
    """Reranked result with new cross-encoder score."""
    original_result: SearchResultProtocol
    rerank_score: float
    original_score: float


class Reranker:
    """
    Cross-encoder reranker for improving search relevance.

    Uses a cross-encoder model that scores query-document pairs directly,
    providing more accurate relevance than bi-encoder embeddings alone.

    Model: cross-encoder/ms-marco-MiniLM-L-6-v2
    - Lightweight and fast (80MB)
    - Trained on MS MARCO passage ranking
    - MIT license
    - ~384 QPS on CPU, much faster on GPU
    """

    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    MAX_LENGTH = 512  # Model's max input length

    def __init__(self, model_name: str | None = None):
        """
        Initialize the reranker with a cross-encoder model.

        Args:
            model_name: Name of the cross-encoder model to use.
                       Defaults to cross-encoder/ms-marco-MiniLM-L-6-v2

        Raises:
            ImportError: If sentence-transformers is not installed
        """
        if CrossEncoder is None:
            raise ImportError(
                "sentence-transformers is required for reranking. "
                "Install with: pip install sentence-transformers"
            )

        self.model_name = model_name or self.DEFAULT_MODEL
        self._model = None

    @property
    def model(self) -> CrossEncoder:
        """Lazy-load the model on first use."""
        if self._model is None:
            self._model = CrossEncoder(self.model_name, max_length=self.MAX_LENGTH)
        return self._model

    def rerank(
        self,
        query: str,
        results: list[SearchResultProtocol],
        top_k: int | None = None
    ) -> list[RerankResult]:
        """
        Rerank search results using cross-encoder scoring.

        Args:
            query: The search query
            results: List of search results to rerank
            top_k: Number of top results to return. If None, returns all.

        Returns:
            List of RerankResult objects ordered by cross-encoder score

        Example:
            >>> from src.rag.search import search
            >>> from src.rag.reranker import Reranker
            >>>
            >>> # Get initial results
            >>> results = search("how to use function calling", top_k=50)
            >>>
            >>> # Rerank
            >>> reranker = Reranker()
            >>> reranked = reranker.rerank(query="how to use function calling",
            ...                            results=results, top_k=5)
            >>>
            >>> for r in reranked:
            ...     print(f"Score: {r.rerank_score:.3f} (was {r.original_score:.3f})")
            ...     print(f"Content: {r.original_result.content[:100]}...")
        """
        if not results:
            return []

        # Prepare query-document pairs for cross-encoder
        # Format: [(query, doc_content), ...]
        pairs = [(query, result.content) for result in results]

        # Score all pairs
        scores = self.model.predict(pairs)

        # Create rerank results
        rerank_results = [
            RerankResult(
                original_result=result,
                rerank_score=float(score),
                original_score=result.score
            )
            for result, score in zip(results, scores)
        ]

        # Sort by rerank score (descending)
        rerank_results.sort(key=lambda x: x.rerank_score, reverse=True)

        # Return top_k if specified
        if top_k is not None:
            return rerank_results[:top_k]

        return rerank_results


def rerank_results(
    query: str,
    results: list[SearchResultProtocol],
    top_k: int | None = None,
    model_name: str | None = None
) -> list[RerankResult]:
    """
    Convenience function for reranking search results.

    Args:
        query: The search query
        results: List of search results to rerank
        top_k: Number of top results to return
        model_name: Optional custom model name

    Returns:
        List of RerankResult objects ordered by cross-encoder score

    Example:
        >>> from src.rag.search import search
        >>> from src.rag.reranker import rerank_results
        >>>
        >>> results = search("function calling", top_k=50)
        >>> reranked = rerank_results("function calling", results, top_k=5)
    """
    reranker = Reranker(model_name=model_name)
    return reranker.rerank(query, results, top_k)


if __name__ == "__main__":
    # Example usage
    print("Testing Cross-Encoder Reranker...")

    try:
        from src.rag.search import search

        # Get initial results with larger pool
        query = "how to use function calling"
        print(f"\nQuery: '{query}'")
        print("-" * 80)

        print("\nFetching initial results (top 20)...")
        results = search(query, top_k=20, collection="gemini")

        if not results:
            print("No results found.")
            exit(1)

        print(f"\nFound {len(results)} initial results")
        print("\nTop 3 before reranking:")
        for i, r in enumerate(results[:3], 1):
            print(f"{i}. [{r.score:.4f}] {r.section}")

        # Rerank
        print("\nReranking with cross-encoder...")
        reranker = Reranker()
        reranked = reranker.rerank(query, results, top_k=5)

        print("\nTop 5 after reranking:")
        for i, r in enumerate(reranked, 1):
            print(f"\n{i}. [{r.rerank_score:.4f}] {r.original_result.section}")
            print(f"   Original score: {r.original_score:.4f}")
            print(f"   Source: {r.original_result.source_url}")
            print(f"   Preview: {r.original_result.content[:150]}...")

        print("\n" + "=" * 80)
        print("Test completed successfully!")

    except ImportError as e:
        print(f"\nError: {e}")
        print("\nTo use reranking, install: pip install sentence-transformers")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
