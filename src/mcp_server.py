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
from src.rag.store import VectorStore

# Known collections
KNOWN_COLLECTIONS = ["gemini", "fastmcp", "claudecode"]

# Create the MCP server
mcp = FastMCP(
    name="Documentation Search",
    log_level="WARNING",  # Reduce startup noise for STDIO transport
    instructions="""
    This server provides access to indexed API documentation for Gemini, FastMCP, and Claude Code.

    USE TOOLS FOR:
    - search_docs: Find documentation by query (semantic + keyword search)
    - list_collections: See what documentation is available

    USE RESOURCES FOR:
    - Browse available collections: docs://collections
    - List pages in a collection: docs://gemini/pages, docs://fastmcp/pages, or docs://claudecode/pages
    - Read a specific page by URL

    AVAILABLE COLLECTIONS:
    - gemini: Google Gemini API documentation (~2000 chunks)
    - fastmcp: FastMCP framework documentation (~1900 chunks)
    - claudecode: Claude Code CLI documentation (~48 pages)

    EXAMPLE QUERIES:
    - "function calling" - find docs about function calling
    - "how to create a tool" - find tool creation guides
    - "MCP server configuration" - find MCP setup docs
    - "hooks" - find Claude Code hooks documentation
    """
)


# =============================================================================
# TOOLS - Actions that search/query the documentation
# =============================================================================

@mcp.tool
def search_docs(
    query: str,
    collection: str = "gemini",
    num_results: int = 5
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
        collection: Which documentation to search. Options:
                   - "gemini" (default): Google Gemini API docs
                   - "fastmcp": FastMCP framework docs
        num_results: Number of results to return (1-20, default: 5).
                    Use more results for broad topics, fewer for specific questions.

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

    if collection not in KNOWN_COLLECTIONS:
        return f"Error: Unknown collection '{collection}'. Available: {', '.join(KNOWN_COLLECTIONS)}"

    num_results = min(max(1, num_results), 20)

    try:
        results = rag_search(
            query=query,
            top_k=num_results,
            collection=collection
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
    found_any = False

    collection_descriptions = {
        "gemini": "Google Gemini API - LLM, function calling, embeddings, multimodal",
        "fastmcp": "FastMCP framework - MCP server/client, tools, resources, auth",
        "claudecode": "Claude Code CLI - hooks, MCP, plugins, settings, workflows"
    }

    for name in KNOWN_COLLECTIONS:
        try:
            store = VectorStore(collection_name=name)
            count = store.count()
            if count > 0:
                found_any = True
                desc = collection_descriptions.get(name, "")
                output.append(f"## {name}")
                output.append(f"- **Documents:** {count} chunks indexed")
                output.append(f"- **Content:** {desc}")
                output.append(f"- **Search:** `search_docs(query, collection=\"{name}\")`\n")
        except Exception:
            pass

    if not found_any:
        output.append("No collections found. Index documentation first:\n")
        output.append("```bash")
        output.append("python -m src.rag.index gemini")
        output.append("python -m src.rag.index fastmcp")
        output.append("```")

    return "\n".join(output)


# =============================================================================
# RESOURCES - Browsable data endpoints
# =============================================================================

@mcp.resource("docs://collections")
def get_collections_resource() -> str:
    """
    List of all available documentation collections.

    Returns JSON with collection names, document counts, and descriptions.
    """
    import json

    collections = []
    collection_descriptions = {
        "gemini": "Google Gemini API documentation",
        "fastmcp": "FastMCP framework documentation",
        "claudecode": "Claude Code CLI documentation"
    }

    for name in KNOWN_COLLECTIONS:
        try:
            store = VectorStore(collection_name=name)
            count = store.count()
            if count > 0:
                collections.append({
                    "name": name,
                    "documents": count,
                    "description": collection_descriptions.get(name, ""),
                    "pages_uri": f"docs://{name}/pages"
                })
        except Exception:
            pass

    return json.dumps({"collections": collections}, indent=2)


@mcp.resource("docs://gemini/pages")
def get_gemini_pages() -> str:
    """List all indexed pages from Gemini documentation."""
    return _get_collection_pages("gemini")


@mcp.resource("docs://fastmcp/pages")
def get_fastmcp_pages() -> str:
    """List all indexed pages from FastMCP documentation."""
    return _get_collection_pages("fastmcp")


def _get_collection_pages(collection: str) -> str:
    """Helper to get unique pages from a collection."""
    import json

    try:
        store = VectorStore(collection_name=collection)
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


@mcp.resource("docs://gemini/search-help")
def gemini_search_help() -> str:
    """Quick reference for searching Gemini documentation."""
    return """# Gemini Documentation Search Help

## Common Search Queries

### Getting Started
- "quickstart tutorial"
- "API key setup"
- "first API call"

### Core Features
- "function calling"
- "structured output JSON"
- "streaming responses"
- "multimodal images video"

### Advanced Topics
- "embeddings semantic search"
- "context caching"
- "token counting"
- "rate limits quotas"
- "safety settings"

### Code Examples
- "Python SDK example"
- "REST API curl"
- "error handling"

## Search Tips
1. Use natural language: "how to use function calling"
2. Combine concepts: "streaming with function calling"
3. Be specific: "token limit for gemini-pro"
"""


@mcp.resource("docs://fastmcp/search-help")
def fastmcp_search_help() -> str:
    """Quick reference for searching FastMCP documentation."""
    return """# FastMCP Documentation Search Help

## Common Search Queries

### Getting Started
- "installation quickstart"
- "create mcp server"
- "hello world example"

### Tools
- "tool decorator"
- "tool parameters"
- "async tools"

### Resources
- "resource decorator"
- "file resource"
- "resource templates"

### Deployment
- "http transport"
- "stdio transport"
- "docker deployment"

### Integration
- "claude code integration"
- "claude desktop setup"

## Search Tips
1. Use natural language: "how to create a tool"
2. Search for decorators: "@mcp.tool decorator"
3. Look for examples: "authentication example"
"""


@mcp.resource("docs://claudecode/pages")
def get_claudecode_pages() -> str:
    """List all indexed pages from Claude Code documentation."""
    return _get_collection_pages("claudecode")


@mcp.resource("docs://claudecode/search-help")
def claudecode_search_help() -> str:
    """Quick reference for searching Claude Code documentation."""
    return """# Claude Code Documentation Search Help

## Common Search Queries

### Getting Started
- "quickstart"
- "installation setup"
- "overview"

### Configuration
- "settings configuration"
- "MCP server setup"
- "memory management"

### Features
- "hooks"
- "plugins"
- "slash commands"
- "subagents"

### IDE Integration
- "VS Code"
- "JetBrains"
- "terminal setup"

### Advanced
- "headless mode"
- "GitHub Actions"
- "enterprise deployment"

## Search Tips
1. Use natural language: "how to configure MCP servers"
2. Search for features: "hooks guide"
3. Look for workflows: "common workflows"
"""


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
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
