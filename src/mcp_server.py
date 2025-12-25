"""MCP Server for documentation search.

Exposes the RAG search functionality as MCP tools and resources that can be used
by Claude Code or other MCP clients from any project.

Tools:
    - search_docs: Semantic + keyword search across documentation
    - list_collections: Show available documentation sources

Resources:
    - docs://collections: List of available collections
    - docs://{collection}/pages: List of all pages in a collection
    - docs://{collection}/page/{url}: Content of a specific page
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import quote, unquote

from fastmcp import FastMCP

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.search import search as rag_search
from src.rag.sqlite_store import SQLiteStore

OUTPUT_PATH = Path(__file__).parent.parent / "output"


def get_available_collections() -> list[str]:
    """Discover all indexed collections from SQLite database."""
    try:
        collections = SQLiteStore.list_collections()
        # Filter to only collections with documents
        return [c for c in collections if SQLiteStore.collection_count(c) > 0]
    except Exception:
        return []


def get_collection_description(name: str) -> str:
    """Get description for a collection from its _index.md or infer from name."""
    index_file = OUTPUT_PATH / name / "_index.md"
    if index_file.exists():
        try:
            content = index_file.read_text()
            # Extract first heading as description
            for line in content.split("\n"):
                if line.startswith("# "):
                    return line[2:].strip()
        except Exception:
            pass
    # Fallback: humanize the collection name
    return f"{name.replace('-', ' ').replace('_', ' ').title()} documentation"

# Create the MCP server
mcp = FastMCP(
    name="Documentation Search",
    instructions="""
    This server provides hybrid semantic + keyword search across indexed API documentation.
    Search uses multi-query expansion and cross-encoder reranking for high-quality results.

    WHEN TO USE THIS SERVER:
    - User asks about API usage, configuration, or features from indexed documentation
    - User needs code examples or implementation guidance from official docs
    - User wants to know "how to" do something with a supported library/framework

    HOW TO SEARCH:
    1. Use search_docs(query, collection) - returns relevant documentation chunks
    2. Query should be natural language describing what you're looking for
    3. Specify the collection parameter to search the right documentation

    AVAILABLE COLLECTIONS (use these as the 'collection' parameter):
    - gemini: Google Gemini API (~2000 chunks) - AI/ML, function calling, embeddings
    - fastmcp: FastMCP framework (~1900 chunks) - MCP server development, tools, resources
    - claudecode: Claude Code CLI (~1000 chunks) - hooks, skills, configuration, IDE integration
    - svelte: Svelte + SvelteKit (~1700 chunks) - runes, components, routing, SSR
    - nextjs: Next.js framework (~3500 chunks) - React, routing, server components
    - stripe: Stripe API (~9300 chunks) - payments, subscriptions, webhooks
    - betterauth: Better Auth (~2000 chunks) - authentication, sessions, OAuth
    - drizzle: Drizzle ORM (~1300 chunks) - database, queries, migrations
    - shadcn: shadcn/ui (~1100 chunks) - React components, styling
    - resend: Resend API (~1200 chunks) - email sending, templates
    - reactemail: React Email (~350 chunks) - email components
    - nextintl: next-intl (~230 chunks) - i18n, translations

    EXAMPLE SEARCHES:
    - search_docs("function calling", "gemini") - Gemini function calling docs
    - search_docs("create MCP tool", "fastmcp") - how to create MCP tools
    - search_docs("hooks configuration", "claudecode") - Claude Code hooks
    - search_docs("reactive state runes", "svelte") - Svelte 5 runes and reactivity
    - search_docs("server components", "nextjs") - Next.js server components
    - search_docs("webhook signatures", "stripe") - Stripe webhook verification
    """
)


# =============================================================================
# TOOLS - Actions that search/query the documentation
# =============================================================================

@mcp.tool
def search_docs(
    query: str,
    collection: str = "gemini",
    num_results: int = 5,
    expand_query: bool = True,
    rerank: bool = True
) -> str:
    """
    Search indexed documentation using hybrid semantic + keyword search.

    This combines vector similarity (semantic understanding) with keyword matching
    to find the most relevant documentation chunks.

    Args:
        query: Natural language search query. Examples:
               - "how to use function calling"
               - "rate limits and pricing"
               - "streaming responses"
               - "error handling best practices"
        collection: Which documentation to search (default: "gemini"). Options:
                   gemini, fastmcp, claudecode, svelte, nextjs, stripe, betterauth,
                   drizzle, shadcn, resend, reactemail, nextintl
        num_results: Number of results to return (1-20, default: 5).
                    Use more results for broad topics, fewer for specific questions.
        expand_query: If True, generate query variations for better recall (default: True).
                     Uses LLM to create alternative phrasings. Slower but may find more relevant results.
        rerank: If True, use cross-encoder reranking for improved relevance (default: True).
               Requires sentence-transformers. Slower but more accurate ranking.

    Returns:
        Formatted markdown with search results, each containing:
        - Relevance score (higher = more relevant)
        - Source URL (original documentation page)
        - Section title
        - Full content chunk

    Example:
        search_docs("function calling", collection="gemini", num_results=3)
    """
    if not query or not query.strip():
        return "Error: Query cannot be empty. Please provide a search term."

    available = get_available_collections()
    if collection not in available:
        if not available:
            return "Error: No collections found. Index documentation first with: python -m src.rag.index <module>"
        return f"Error: Unknown collection '{collection}'. Available: {', '.join(sorted(available))}"

    num_results = min(max(1, num_results), 20)

    try:
        results = rag_search(
            query=query,
            top_k=num_results,
            collection=collection,
            expand_query=expand_query,
            rerank=rerank
        )

        if not results:
            return f"No results found for '{query}' in '{collection}' documentation.\n\nTry:\n- Different keywords\n- Broader search terms\n- Checking if the collection is indexed"

        output = [f"# Search Results for '{query}'\n"]
        output.append(f"**Collection:** {collection} | **Results:** {len(results)}\n")

        for i, result in enumerate(results, 1):
            output.append(f"## [{i}] {result.section or 'Untitled'}")
            output.append(f"**Score:** {result.score:.3f} | **Source:** {result.source_url}\n")
            output.append(result.content)
            output.append("\n---\n")

        return "\n".join(output)

    except Exception as e:
        return f"Error searching '{collection}': {str(e)}\n\nMake sure Ollama is running with bge-m3 model."


@mcp.tool
def list_collections() -> str:
    """
    List all available documentation collections with their document counts.

    Use this to discover what documentation sources are indexed and available
    for searching.

    Returns:
        Markdown list of collections with:
        - Collection name (use this in search_docs)
        - Number of indexed document chunks
        - Brief description of the documentation source

    Example output:
        - gemini: 2077 documents (Google Gemini API)
        - fastmcp: 1891 documents (FastMCP framework)
    """
    output = ["# Available Documentation Collections\n"]

    available = get_available_collections()

    if not available:
        output.append("No collections found. Index documentation first:\n")
        output.append("```bash")
        output.append("python -m src.rag.index <module>")
        output.append("```")
        return "\n".join(output)

    for name in sorted(available):
        try:
            count = SQLiteStore.collection_count(name)
            desc = get_collection_description(name)
            output.append(f"## {name}")
            output.append(f"- **Documents:** {count} chunks indexed")
            output.append(f"- **Content:** {desc}")
            output.append(f"- **Search:** `search_docs(query, collection=\"{name}\")`\n")
        except Exception:
            pass

    return "\n".join(output)


# =============================================================================
# RESOURCES - Browsable data endpoints
# =============================================================================

@mcp.resource("docs://collections")
def get_collections_resource() -> str:
    """
    JSON list of all available documentation collections.

    Returns:
        JSON object with collection metadata including:
        - name: Collection identifier for search_docs
        - documents: Number of indexed chunks
        - description: What documentation this covers
        - pages_uri: URI to list all pages in this collection

    Use this to programmatically discover available documentation sources.
    """
    import json

    collections = []
    available = get_available_collections()

    for name in sorted(available):
        try:
            count = SQLiteStore.collection_count(name)
            collections.append({
                "name": name,
                "documents": count,
                "description": get_collection_description(name),
                "pages_uri": f"docs://{name}/pages"
            })
        except Exception:
            pass

    return json.dumps({"collections": collections}, indent=2)


@mcp.resource("docs://{collection}/pages")
def get_collection_pages_resource(collection: str) -> str:
    """
    List all indexed pages from a documentation collection.

    Args:
        collection: The collection name. Options: gemini, fastmcp, claudecode, svelte,
                   nextjs, stripe, betterauth, drizzle, shadcn, resend, reactemail, nextintl

    Returns:
        JSON object with:
        - collection: The collection name
        - page_count: Total number of unique pages
        - pages: Array of {url, title} objects for each documentation page

    Use this to browse what documentation pages are available before searching.
    """
    available = get_available_collections()
    if collection not in available:
        import json
        return json.dumps({"error": f"Unknown collection: {collection}", "available": sorted(available)})
    return _get_collection_pages(collection)


def _get_collection_pages(collection: str) -> str:
    """Helper to get unique pages from a collection."""
    import json

    try:
        store = SQLiteStore(collection_name=collection)
        all_docs = store.get_all_documents()

        # Extract unique source URLs
        pages = {}
        for doc in all_docs:
            url = doc.get("metadata", {}).get("source_url", "")
            if url and url not in pages:
                section = doc.get("metadata", {}).get("section", "")
                pages[url] = {
                    "url": url,
                    "title": section.split(" > ")[0] if section else url.split("/")[-1],
                }

        return json.dumps({
            "collection": collection,
            "page_count": len(pages),
            "pages": list(pages.values())
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        description="Documentation Search MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with STDIO (for Claude Code)
  python -m src.mcp_server

  # Run as HTTP server
  python -m src.mcp_server --transport http --port 8000

  # Run for Docker (bind to all interfaces)
  python -m src.mcp_server --transport http --host 0.0.0.0 --port 8000
        """
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio for Claude Code)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP transport (default: 8000)"
    )

    args = parser.parse_args()

    if args.transport == "http":
        print(f"Starting HTTP server at http://{args.host}:{args.port}/mcp")
        print(f"\nAvailable endpoints:")
        print(f"  Tools:     POST http://{args.host}:{args.port}/mcp")
        print(f"  Resources: GET  http://{args.host}:{args.port}/mcp")
        mcp.run(transport="http", host=args.host, port=args.port, log_level="WARNING")
    else:
        mcp.run(log_level="WARNING")


if __name__ == "__main__":
    main()
