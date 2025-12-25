"""Indexing CLI for RAG documentation system.

Processes markdown files from output directories, chunks them,
generates embeddings, and stores in SQLite for semantic search.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .chunker import chunk_markdown
from .embedder import Embedder
from .sqlite_store import SQLiteStore


def index_documents(source: str, clear: bool = False, output_dir: Optional[Path] = None) -> None:
    """Index all documents from output/<source>/ directory.

    Args:
        source: Documentation source (e.g., "gemini")
        clear: Whether to clear existing index first
        output_dir: Custom output directory (default: output/<source>/)
    """
    # Determine output directory
    if output_dir is None:
        output_dir = Path("output") / source

    # Validate output directory exists
    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}", file=sys.stderr)
        print(f"Run 'python -m src.main fetch {source}' first to download documentation.", file=sys.stderr)
        sys.exit(1)

    # Find all markdown files
    markdown_files = list(output_dir.glob("*.md"))

    if not markdown_files:
        print(f"Error: No markdown files found in {output_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(markdown_files)} markdown files in {output_dir}")

    # Initialize components
    print("\nInitializing embedder and SQLite store...")
    try:
        embedder = Embedder()
        store = SQLiteStore(collection_name=source)
    except Exception as e:
        print(f"Error initializing components: {e}", file=sys.stderr)
        print("\nMake sure Ollama is running with the bge-m3 model:", file=sys.stderr)
        print("  ollama pull bge-m3", file=sys.stderr)
        sys.exit(1)

    # Clear existing index if requested
    if clear:
        print(f"\nClearing existing index for '{source}'...")
        store.clear()
        print("Index cleared.")

    # Process all files
    print(f"\nProcessing {len(markdown_files)} files...")

    all_chunks = []
    total_chunks = 0

    for i, filepath in enumerate(markdown_files, 1):
        try:
            # Chunk the file
            chunks = chunk_markdown(filepath)
            all_chunks.extend(chunks)
            total_chunks += len(chunks)

            # Show progress
            print(f"  [{i}/{len(markdown_files)}] {filepath.name}: {len(chunks)} chunks")

        except Exception as e:
            print(f"  Warning: Failed to process {filepath.name}: {e}", file=sys.stderr)
            continue

    if not all_chunks:
        print("\nError: No chunks generated from markdown files.", file=sys.stderr)
        sys.exit(1)

    print(f"\nGenerated {total_chunks} chunks total")

    # Generate embeddings in batches
    print("\nGenerating embeddings...")
    batch_size = 20  # Smaller batches for stability
    all_embeddings = []

    for i in range(0, len(all_chunks), batch_size):
        batch_chunks = all_chunks[i:i + batch_size]
        batch_texts = [chunk.content for chunk in batch_chunks]

        try:
            batch_embeddings = embedder.embed(batch_texts)
            all_embeddings.extend(batch_embeddings)

            # Show progress
            processed = min(i + batch_size, len(all_chunks))
            print(f"  Embedded {processed}/{len(all_chunks)} chunks...")

        except Exception as e:
            print(f"\nError generating embeddings: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Generated {len(all_embeddings)} embeddings")

    # Store in SQLite database
    print("\nStoring in SQLite...")
    try:
        store.add(all_chunks, all_embeddings)
        print(f"Successfully indexed {len(all_chunks)} chunks")
    except Exception as e:
        print(f"\nError storing embeddings: {e}", file=sys.stderr)
        sys.exit(1)

    # Show final stats
    total_docs = store.count()
    print(f"\nIndexing complete!")
    print(f"Total documents in '{source}' collection: {total_docs}")


def show_status(source: str) -> None:
    """Show index statistics.

    Args:
        source: Documentation source (e.g., "gemini")
    """
    try:
        store = SQLiteStore(collection_name=source)
        count = store.count()

        print(f"\nIndex Status for '{source}':")
        print(f"  Total documents: {count}")

        if count == 0:
            print(f"\nNo documents indexed yet. Run:")
            print(f"  python -m src.rag.index {source}")

    except Exception as e:
        print(f"Error getting status: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for indexing CLI."""
    parser = argparse.ArgumentParser(
        description="Index documentation for RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index Gemini documentation
  python -m src.rag.index gemini

  # Clear and re-index
  python -m src.rag.index --clear gemini

  # Show index statistics
  python -m src.rag.index --status gemini
        """
    )

    parser.add_argument(
        "source",
        help="Documentation source (e.g., gemini)"
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing index before indexing"
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show index status only (no indexing)"
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Custom output directory (default: output/<source>)"
    )

    args = parser.parse_args()

    # Show status only
    if args.status:
        show_status(args.source)
        return

    # Index documents
    index_documents(
        source=args.source,
        clear=args.clear,
        output_dir=args.output
    )


if __name__ == "__main__":
    main()
