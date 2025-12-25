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
│   │   ├── fastmcp/
│   │   │   ├── __init__.py
│   │   │   ├── module.py       # FastMCP documentation fetcher
│   │   │   └── config.py       # FastMCP URLs, sitemap config
│   │   ├── betterauth/
│   │   │   ├── __init__.py
│   │   │   ├── module.py       # Better Auth documentation fetcher
│   │   │   └── config.py       # Better Auth URLs, llms.txt config
│   │   ├── drizzle/
│   │   │   ├── __init__.py
│   │   │   ├── module.py       # Drizzle ORM documentation fetcher
│   │   │   └── config.py       # Drizzle URLs, HTML→markdown config
│   │   ├── nextintl/
│   │   │   ├── __init__.py
│   │   │   ├── module.py       # next-intl documentation fetcher
│   │   │   └── config.py       # next-intl URLs, sitemap config
│   │   ├── resend/
│   │   │   ├── __init__.py
│   │   │   ├── module.py       # Resend documentation fetcher
│   │   │   └── config.py       # Resend URLs, single-file split config
│   │   ├── reactemail/
│   │   │   ├── __init__.py
│   │   │   ├── module.py       # React Email documentation fetcher
│   │   │   └── config.py       # React Email URLs, sitemap config
│   │   └── shadcn/
│   │       ├── __init__.py
│   │       ├── module.py       # shadcn/ui documentation fetcher
│   │       └── config.py       # shadcn URLs, llms.txt + .md suffix
│   └── rag/
│       ├── __init__.py
│       ├── chunker.py          # Markdown-aware chunking (header-based)
│       ├── embedder.py         # Ollama bge-m3 embeddings
│       ├── sqlite_store.py     # SQLite + sqlite-vec vector store
│       ├── search.py           # Hybrid search (semantic + keyword)
│       ├── query_expander.py   # Multi-query expansion using LLM
│       ├── reranker.py         # Cross-encoder reranking (optional)
│       └── index.py            # Indexing CLI
├── output/                     # Fetched documentation output
│   └── gemini/
├── data/
│   └── docs.db                 # SQLite vector database
├── requirements.txt
├── pyproject.toml
└── CLAUDE.md
```

## Dependencies

- Python 3.12+
- Ollama with required models:
  - `bge-m3` for embeddings (`ollama pull bge-m3`)
  - `llama3.2` for query expansion (optional, `ollama pull llama3.2`)
- SQLite with sqlite-vec extension (included)
- sentence-transformers for reranking (optional, `pip install sentence-transformers`)

## Usage

```bash
source .venv/bin/activate

# Fetch documentation
python -m src.main fetch gemini
python -m src.main fetch fastmcp
python -m src.main fetch betterauth
python -m src.main fetch drizzle
python -m src.main fetch nextintl
python -m src.main fetch resend
python -m src.main fetch reactemail
python -m src.main fetch shadcn

# Index for search (requires Ollama running)
python -m src.rag.index gemini
python -m src.rag.index fastmcp
python -m src.rag.index betterauth
python -m src.rag.index drizzle
python -m src.rag.index nextintl
python -m src.rag.index resend
python -m src.rag.index reactemail
python -m src.rag.index shadcn
python -m src.rag.index --clear gemini  # Clear and re-index

# Search documentation
python -m src.main search "function calling"
python -m src.main search "how to create a tool" -c fastmcp      # Search FastMCP docs
python -m src.main search "two factor auth" -c betterauth        # Search Better Auth docs
python -m src.main search "migrations" -c drizzle                # Search Drizzle docs
python -m src.main search "locale" -c nextintl                   # Search next-intl docs

# Advanced search options
python -m src.main search "query" -n 10                          # More results
python -m src.main search "query" -v                             # Verbose with rank info
python -m src.main search "query" --expand                       # Multi-query expansion for better recall
python -m src.main search "query" --rerank                       # Cross-encoder reranking for better relevance
python -m src.main search "query" --expand --rerank              # Combine both for best results
python -m src.main search "send email" -c resend                 # Search Resend docs
python -m src.main search "button component" -c reactemail       # Search React Email docs
python -m src.main search "dialog component" -c shadcn           # Search shadcn/ui docs
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
3. **Store** (`src/rag/sqlite_store.py`): SQLite + sqlite-vec + FTS5 for hybrid search
4. **Search** (`src/rag/search.py`): Hybrid search using reciprocal rank fusion (RRF)
5. **Query Expander** (`src/rag/query_expander.py`): Multi-query expansion using LLM (optional)
6. **Reranker** (`src/rag/reranker.py`): Cross-encoder reranking for improved relevance (optional)

Each documentation source gets its own collection, allowing filtered searches.

### Search Features

- **Hybrid Search**: Combines semantic (vector) and keyword (FTS5) search with RRF fusion
- **Multi-Query Expansion** (optional): Uses LLM to generate query variations for better recall
  - Requires Ollama with a small model (default: llama3.2)
  - Generates 3-5 alternative phrasings of your query
  - Searches with each variation and combines results using RRF
- **Cross-Encoder Reranking** (optional): Uses transformer model to rerank results
  - Requires `sentence-transformers` package
  - Provides more accurate relevance scoring
  - Can be combined with query expansion for best results

## Gemini Module Notes

- Base URL: `https://ai.google.dev/gemini-api/docs`
- Markdown trick: Append `.md.txt` to URLs for clean markdown
- Navigation: Uses `devsite-book-nav` component with sidebar structure

## Better Auth Module Notes

- Base URL: `https://www.better-auth.com`
- Discovery: Parses `llms.txt` file which lists all documentation pages
- Markdown: Direct access via `/llms.txt/docs/*.md` paths
- Coverage: ~150 pages including adapters, plugins, integrations, and guides

## Drizzle ORM Module Notes

- Base URL: `https://orm.drizzle.team`
- Discovery: Parses `llms.txt` file which lists all documentation URLs
- Conversion: Fetches HTML pages and converts to markdown via `html2text`
- Coverage: ~180 pages covering schemas, migrations, queries, and database integrations

## next-intl Module Notes

- Base URL: `https://next-intl.dev`
- Discovery: Parses sitemap XML for `/docs/` URLs
- Conversion: Fetches HTML pages and converts to markdown via `html2text`
- Coverage: ~30 pages covering i18n setup, routing, messages, and formatting

## Resend Module Notes

- Base URL: `https://resend.com`
- Discovery: Single `llms-full.txt` file containing all documentation
- Processing: Splits on `# ` headers, extracts source URLs, saves as separate files
- Coverage: ~227 sections covering API reference, SDKs, integrations, and guides

## React Email Module Notes

- Base URL: `https://react.email`
- Discovery: Parses sitemap XML at `/docs/sitemap.xml`
- Conversion: Fetches HTML pages and converts to markdown via `html2text`
- Coverage: ~52 pages covering components, integrations, setup, and utilities

## shadcn/ui Module Notes

- Base URL: `https://ui.shadcn.com`
- Discovery: Parses `llms.txt` file which lists all documentation URLs
- Markdown: Appends `.md` suffix to URLs for direct markdown access
- Coverage: ~93 pages covering components, installation, theming, forms, and registry

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
| `docs://collections` | JSON list of all collections (auto-discovered) |
| `docs://{collection}/pages` | List of all pages in a collection |

Collections are auto-discovered from the SQLite database - no code changes needed when adding new documentation sources.

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
