"""
Ollama embedder for RAG (Retrieval-Augmented Generation).

This module provides an interface to generate text embeddings using a local Ollama instance.
Embeddings are vector representations of text that enable semantic search and similarity matching.
"""

import sys
from typing import Optional

try:
    import ollama
except ImportError:
    print("Error: ollama package not found. Install it with: pip install ollama", file=sys.stderr)
    sys.exit(1)


class Embedder:
    """
    Ollama embedder for generating text embeddings.

    Connects to a local Ollama instance to generate embedding vectors using
    the specified model. Supports both single and batch embedding operations.

    Attributes:
        model (str): Name of the embedding model to use (default: "bge-m3")
        host (str): URL of the Ollama instance (default: "http://localhost:11434")
    """

    def __init__(self, model: str = "bge-m3", host: str = "http://localhost:11434"):
        """
        Initialize the Ollama embedder.

        Args:
            model: The embedding model to use (default: "bge-m3")
            host: The Ollama instance URL (default: "http://localhost:11434")

        Raises:
            ConnectionError: If unable to connect to the Ollama instance
        """
        self.model = model
        self.host = host
        self._client = ollama.Client(host=host)

        # Verify connection and model availability
        self._verify_connection()

    def _verify_connection(self) -> None:
        """
        Verify that Ollama is running and the model is available.

        Raises:
            ConnectionError: If Ollama is not running or unreachable
            ValueError: If the specified model is not available
        """
        try:
            # Try to list available models to verify connection
            models_response = self._client.list()

            # Handle different response formats
            if hasattr(models_response, 'models'):
                models = models_response.models
            elif isinstance(models_response, dict):
                models = models_response.get('models', [])
            else:
                models = []

            # Extract model names - handle both dict and object formats
            model_names = []
            for m in models:
                if hasattr(m, 'name'):
                    model_names.append(m.name)
                elif isinstance(m, dict) and 'name' in m:
                    model_names.append(m['name'])
                elif isinstance(m, dict) and 'model' in m:
                    model_names.append(m['model'])

            # Check if our model is available
            # Models can have tags like "bge-m3:latest", so check for partial match
            model_found = any(self.model in name for name in model_names)

            if model_names and not model_found:
                print(
                    f"Warning: Model '{self.model}' not found in Ollama.\n"
                    f"Available models: {', '.join(model_names)}\n"
                    f"Pull the model with: ollama pull {self.model}",
                    file=sys.stderr
                )
                # Don't raise an error, let it fail on actual embed call
                # This allows the model to be pulled after initialization

        except ollama.ResponseError as e:
            raise ConnectionError(
                f"Failed to connect to Ollama at {self.host}. "
                f"Make sure Ollama is running.\n"
                f"Error: {e}"
            ) from e
        except Exception as e:
            raise ConnectionError(
                f"Unexpected error connecting to Ollama at {self.host}: {e}"
            ) from e

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts in batch.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors, where each vector is a list of floats.
            The outer list has the same length as the input texts list.

        Raises:
            ValueError: If texts is empty or contains invalid input
            ConnectionError: If Ollama connection fails
            RuntimeError: If embedding generation fails

        Example:
            >>> embedder = Embedder()
            >>> vectors = embedder.embed(["Hello world", "Goodbye world"])
            >>> len(vectors)
            2
            >>> len(vectors[0])  # Vector dimension (depends on model)
            1024
        """
        if not texts:
            raise ValueError("texts list cannot be empty")

        if not all(isinstance(t, str) for t in texts):
            raise ValueError("All items in texts must be strings")

        try:
            response = self._client.embed(model=self.model, input=texts)
            embeddings = response.get('embeddings', [])

            if not embeddings:
                raise RuntimeError(
                    f"No embeddings returned from Ollama for model '{self.model}'. "
                    f"The model may not be available. Try: ollama pull {self.model}"
                )

            return embeddings

        except ollama.ResponseError as e:
            if "model" in str(e).lower() and "not found" in str(e).lower():
                raise RuntimeError(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Pull it with: ollama pull {self.model}"
                ) from e
            raise ConnectionError(f"Ollama request failed: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to generate embeddings: {e}") from e

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single query text.

        This is a convenience method for embedding a single string.
        It calls embed() internally and extracts the first result.

        Args:
            query: The text query to embed

        Returns:
            A single embedding vector as a list of floats

        Raises:
            ValueError: If query is empty or not a string
            ConnectionError: If Ollama connection fails
            RuntimeError: If embedding generation fails

        Example:
            >>> embedder = Embedder()
            >>> vector = embedder.embed_query("What is machine learning?")
            >>> len(vector)  # Vector dimension (depends on model)
            1024
        """
        if not isinstance(query, str):
            raise ValueError("query must be a string")

        if not query.strip():
            raise ValueError("query cannot be empty")

        # Use batch embed with single item and extract first result
        embeddings = self.embed([query])
        return embeddings[0]

    def get_model_info(self) -> dict:
        """
        Get information about the current embedding model.

        Returns:
            Dictionary containing model information including name and dimensions

        Example:
            >>> embedder = Embedder()
            >>> info = embedder.get_model_info()
            >>> print(info['model'])
            bge-m3
        """
        # Embed a test string to determine vector dimensions
        test_embedding = self.embed_query("test")

        return {
            "model": self.model,
            "host": self.host,
            "dimensions": len(test_embedding)
        }


if __name__ == "__main__":
    # Example usage and testing
    print("Testing Ollama Embedder...")

    try:
        # Initialize embedder
        embedder = Embedder()
        print(f"Connected to Ollama at {embedder.host}")

        # Get model info
        info = embedder.get_model_info()
        print(f"Model: {info['model']}")
        print(f"Embedding dimensions: {info['dimensions']}")

        # Test single query embedding
        print("\nTesting single query embedding...")
        query = "What is the capital of France?"
        query_vector = embedder.embed_query(query)
        print(f"Query: '{query}'")
        print(f"Vector length: {len(query_vector)}")
        print(f"First 5 dimensions: {query_vector[:5]}")

        # Test batch embedding
        print("\nTesting batch embedding...")
        texts = [
            "The sky is blue because of Rayleigh scattering",
            "Grass is green because of chlorophyll",
            "The ocean appears blue due to water absorption"
        ]
        vectors = embedder.embed(texts)
        print(f"Embedded {len(vectors)} texts")
        for i, text in enumerate(texts):
            print(f"  {i+1}. '{text[:50]}...' -> vector of length {len(vectors[i])}")

        print("\nAll tests passed!")

    except ConnectionError as e:
        print(f"\nConnection Error: {e}")
        print("\nMake sure Ollama is running:")
        print("  - Check if Ollama is installed: ollama --version")
        print("  - Start Ollama if needed (it usually runs automatically)")
        print(f"  - Verify it's accessible at http://localhost:11434")
        sys.exit(1)

    except RuntimeError as e:
        print(f"\nRuntime Error: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\nUnexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
