"""Query expansion using LLM to generate alternative phrasings for better recall."""

import sys
from typing import Optional

try:
    import ollama
except ImportError:
    print("Error: ollama package not found. Install it with: pip install ollama", file=sys.stderr)
    sys.exit(1)


class QueryExpander:
    """
    Expand search queries into multiple variations using a small/fast LLM.

    This improves search recall by generating alternative phrasings and
    reformulations of the user's query. The expanded queries are then
    combined using Reciprocal Rank Fusion (RRF).

    Uses a lightweight model (default: llama3.2) for fast generation.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
        num_variations: int = 3
    ):
        """
        Initialize the query expander.

        Args:
            model: LLM model to use for generation (default: "llama3.2")
                   Other small/fast options: "qwen2.5:0.5b", "phi3", "gemma2:2b"
            host: Ollama instance URL (default: "http://localhost:11434")
            num_variations: Number of variations to generate (default: 3)
        """
        self.model = model
        self.host = host
        self.num_variations = num_variations
        self._client = ollama.Client(host=host)

    def expand(self, query: str) -> list[str]:
        """
        Expand a query into multiple variations.

        Args:
            query: Original search query

        Returns:
            List of query strings including the original (first item)

        Example:
            >>> expander = QueryExpander()
            >>> queries = expander.expand("how to call functions")
            >>> print(queries)
            [
                "how to call functions",
                "function calling syntax",
                "invoking functions tutorial",
                "execute function examples"
            ]
        """
        if not query or not query.strip():
            return [query]

        query = query.strip()

        # Build prompt for query expansion
        prompt = self._build_prompt(query)

        try:
            # Generate variations using Ollama
            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.7,  # Some creativity, but not too much
                    "top_p": 0.9,
                    "num_predict": 100,  # Limit output length for speed
                }
            )

            # Parse variations from response
            variations = self._parse_response(response.get('response', ''))

            # Always include original query first
            result = [query]

            # Add valid variations
            for var in variations:
                if var and var.strip() and var.strip() != query:
                    result.append(var.strip())

            # Limit to requested number of variations + original
            return result[:self.num_variations + 1]

        except ollama.ResponseError as e:
            print(f"Warning: Query expansion failed: {e}", file=sys.stderr)
            print(f"Hint: Make sure model '{self.model}' is available: ollama pull {self.model}", file=sys.stderr)
            # Fallback to original query only
            return [query]

        except Exception as e:
            print(f"Warning: Unexpected error during query expansion: {e}", file=sys.stderr)
            # Fallback to original query only
            return [query]

    def _build_prompt(self, query: str) -> str:
        """
        Build prompt for query expansion.

        Args:
            query: Original query

        Returns:
            Prompt string for the LLM
        """
        return f"""Generate {self.num_variations} alternative phrasings for this search query. Return only the queries, one per line.

Original query: {query}

Alternative queries:"""

    def _parse_response(self, response: str) -> list[str]:
        """
        Parse LLM response into list of query variations.

        Args:
            response: Raw LLM response text

        Returns:
            List of parsed query strings
        """
        if not response:
            return []

        # Split by newlines and clean up
        lines = response.strip().split('\n')
        variations = []

        for line in lines:
            # Clean up common prefixes/markers
            line = line.strip()

            # Remove numbering (1., 2., etc.)
            if line and line[0].isdigit() and '.' in line[:4]:
                line = line.split('.', 1)[1].strip()

            # Remove bullet points
            line = line.lstrip('•-*').strip()

            # Remove quotes
            line = line.strip('"\'')

            # Skip empty lines or meta-comments
            if not line or line.lower().startswith(('here', 'alternative', 'variation', 'query')):
                continue

            variations.append(line)

        return variations


if __name__ == "__main__":
    # Example usage and testing
    print("Testing Query Expander...")

    try:
        # Initialize expander
        expander = QueryExpander()
        print(f"Using model: {expander.model}")
        print()

        # Test queries
        test_queries = [
            "how to call functions",
            "rate limits and pricing",
            "streaming responses",
            "error handling best practices"
        ]

        for query in test_queries:
            print(f"Original: \"{query}\"")
            expanded = expander.expand(query)
            print(f"Expanded to {len(expanded)} queries:")
            for i, q in enumerate(expanded):
                marker = "[original]" if i == 0 else f"[var {i}]"
                print(f"  {marker} {q}")
            print()

        print("All tests passed!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
