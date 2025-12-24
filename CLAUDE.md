# Documentation Fetcher

A modular system for fetching API documentation and enabling semantic search via RAG.

## Purpose

Fetch complete, up-to-date documentation from various API providers (starting with Gemini) in clean markdown format, then index for semantic search. Useful for:
- Feeding documentation into LLMs for context
- Semantic search across documentation
- Offline documentation access
- Building custom search/reference tools

## Project Structure

```
documentation/
├── .venv/                      # Python virtual environment (Python 3.12)
├── src/
│   ├── __init__.py
│   ├── main.py                 # CLI entry point (fetch + search commands)
│   ├── mcp_server.py           # MCP server for Claude Code integration
│   ├── core/
│   │   ├── __init__.py
│   │   ├── fetcher.py          # Base HTTP/markdown fetching logic
│   │   └── parser.py           # Base navigation parsing logic
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract base class for modules
│   │   ├── gemini/
│   │   │   ├── __init__.py
│   │   │   ├── module.py       # Gemini-specific implementation
│   │   │   └── config.py       # Gemini URLs, selectors, etc.
│   │   └── fastmcp/
│   │       ├── __init__.py
│   │       ├── module.py       # FastMCP documentation fetcher
│   │       └── config.py       # FastMCP URLs, sitemap config
│   └── rag/
│       ├── __init__.py
│       ├── chunker.py          # Markdown-aware chunking (header-based)
│       ├── embedder.py         # Ollama bge-m3 embeddings
│       ├── store.py            # ChromaDB vector store
│       ├── search.py           # Hybrid search (semantic + keyword)
│       └── index.py            # Indexing CLI
├── output/                     # Fetched documentation output
│   └── gemini/
├── data/
│   └── chromadb/               # Vector database storage
├── requirements.txt
├── pyproject.toml
└── CLAUDE.md
```

## Dependencies

- Python 3.12 (required for ChromaDB compatibility)
- Ollama with bge-m3 model (`ollama pull bge-m3`)
- ChromaDB for vector storage

## Usage

```bash
source .venv/bin/activate

# Fetch documentation
python -m src.main fetch gemini
python -m src.main fetch fastmcp

# Index for search (requires Ollama running)
python -m src.rag.index gemini
python -m src.rag.index fastmcp
python -m src.rag.index --clear gemini  # Clear and re-index

# Search documentation
python -m src.main search "function calling"
python -m src.main search "how to create a tool" -c fastmcp  # Search FastMCP docs
python -m src.main search "rate limits" -n 10                # More results
python -m src.main search "query" -v                         # Verbose with rank info
```

## Module Architecture

Each documentation source (Gemini, OpenAI, Anthropic, etc.) is implemented as a module that:
1. Parses the navigation/sitemap to discover all documentation pages
2. Fetches each page in markdown format
3. Handles source-specific quirks (e.g., Google's `.md.txt` suffix for markdown)

Modules inherit from a base class in `src/modules/base.py`.

## RAG System

The RAG system enables semantic search across indexed documentation:

1. **Chunker** (`src/rag/chunker.py`): Splits markdown by headers, preserves code blocks
2. **Embedder** (`src/rag/embedder.py`): Generates embeddings via Ollama bge-m3 (1024 dims)
3. **Store** (`src/rag/store.py`): ChromaDB with per-source collections
4. **Search** (`src/rag/search.py`): Hybrid search using reciprocal rank fusion

Each documentation source gets its own collection, allowing filtered searches.

## Gemini Module Notes

- Base URL: `https://ai.google.dev/gemini-api/docs`
- Markdown trick: Append `.md.txt` to URLs for clean markdown
- Navigation: Uses `devsite-book-nav` component with sidebar structure

## MCP Server

The MCP server (`src/mcp_server.py`) exposes documentation search as tools that Claude Code can use from any project.

### Available Tools

| Tool | Description |
|------|-------------|
| `search_docs` | Search documentation with query, collection, and num_results parameters |
| `list_collections` | List available documentation collections with document counts |

### Available Resources

| Resource URI | Description |
|--------------|-------------|
| `docs://collections` | JSON list of all collections |
| `docs://gemini/pages` | List of all Gemini documentation pages |
| `docs://fastmcp/pages` | List of all FastMCP documentation pages |
| `docs://gemini/search-help` | Search tips for Gemini docs |
| `docs://fastmcp/search-help` | Search tips for FastMCP docs |

### Install in Claude Code

**IMPORTANT**: MCP configuration requires **absolute paths**. The `cwd` field is NOT supported.

**Option 1: Using Claude CLI (recommended)**
```bash
# Replace /path/to/documentation with your actual path
claude mcp add docs-search --scope user --transport stdio -- \
  /path/to/documentation/.venv/bin/python \
  /path/to/documentation/src/mcp_server.py
```

**Option 2: Add to ~/.claude.json manually**
```json
{
  "mcpServers": {
    "docs-search": {
      "command": "/path/to/documentation/.venv/bin/python",
      "args": ["/path/to/documentation/src/mcp_server.py"]
    }
  }
}
```

**Common mistakes to avoid:**
- Do NOT use `cwd` - it's not a valid MCP field
- Do NOT use relative paths - they resolve from the caller's directory
- Do NOT use `-m src.mcp_server` - requires being in the project directory

### Verify Installation

```bash
# Check server is registered
claude mcp list

# In Claude Code, check connection status
/mcp
```

### Run as HTTP Server (Docker/Remote)

```bash
# Local testing
python -m src.mcp_server --transport http --port 8000

# Docker/remote (bind to all interfaces)
python -m src.mcp_server --transport http --host 0.0.0.0 --port 8000
```

### Usage from Claude Code

Once installed, Claude can use the tools from any project:

```
Search the gemini docs for "function calling"
→ Uses search_docs(query="function calling", collection="gemini")

What documentation collections are available?
→ Uses list_collections()

Search fastmcp docs for "how to create a tool"
→ Uses search_docs(query="how to create a tool", collection="fastmcp")
```
