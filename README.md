# Documentation Fetcher & RAG Search

A modular system for fetching API documentation and enabling semantic search via RAG (Retrieval-Augmented Generation). Designed to give AI coding assistants like Claude access to up-to-date documentation from any project.

## Features

- **Fetch Documentation**: Download complete documentation from API providers in markdown format
- **Semantic Search**: Hybrid search combining vector embeddings with keyword matching
- **MCP Server**: Expose search as tools accessible from Claude Code in any project
- **Modular Design**: Easy to add new documentation sources

## Supported Documentation Sources

| Source | Documents | Description |
|--------|-----------|-------------|
| Gemini | ~2000 | Google Gemini API - LLM, function calling, embeddings, multimodal |
| FastMCP | ~1900 | FastMCP framework - MCP servers, tools, resources, authentication |

## Quick Start

### Prerequisites

- Python 3.12+
- [Ollama](https://ollama.ai/) with bge-m3 model
- Claude Code (for MCP integration)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd documentation

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Pull the embedding model
ollama pull bge-m3
```

### Fetch & Index Documentation

```bash
# Fetch documentation
python -m src.main fetch gemini
python -m src.main fetch fastmcp

# Index for search (requires Ollama running)
python -m src.rag.index gemini
python -m src.rag.index fastmcp
```

### Search Documentation

```bash
# Search Gemini docs
python -m src.main search "function calling"

# Search FastMCP docs
python -m src.main search "how to create a tool" -c fastmcp

# More results
python -m src.main search "rate limits" -n 10
```

## MCP Server Integration

The MCP server exposes documentation search as tools that Claude Code can use from any project.

### Install in Claude Code

**IMPORTANT**: MCP configuration requires **absolute paths**. The `cwd` field is NOT supported by Claude Code.

**Option 1: Using Claude CLI (recommended)**
```bash
# Replace /path/to/documentation with your actual absolute path
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
- Do NOT use `cwd` - it's not a valid MCP configuration field
- Do NOT use relative paths - they resolve from the caller's directory
- Do NOT use `-m src.mcp_server` - this requires being in the project directory

### Verify Installation

```bash
# Check server is registered
claude mcp list

# In Claude Code, check connection status
/mcp
```

### Available Tools

| Tool | Description |
|------|-------------|
| `search_docs(query, collection, num_results)` | Search documentation with hybrid semantic + keyword search |
| `list_collections()` | List available documentation collections |

### Available Resources

| Resource URI | Description |
|--------------|-------------|
| `docs://collections` | JSON list of all collections |
| `docs://gemini/pages` | List of all Gemini documentation pages |
| `docs://fastmcp/pages` | List of all FastMCP documentation pages |
| `docs://gemini/search-help` | Search tips for Gemini docs |
| `docs://fastmcp/search-help` | Search tips for FastMCP docs |

### Usage from Claude Code

Once installed, you can ask Claude from any project:

- "Search the gemini docs for function calling"
- "What documentation collections are available?"
- "Search fastmcp for how to create tools"
- "Find rate limit information in gemini docs"

## Project Structure

```
documentation/
├── src/
│   ├── main.py                 # CLI entry point
│   ├── mcp_server.py           # MCP server for Claude Code
│   ├── core/
│   │   ├── fetcher.py          # HTTP/markdown fetching
│   │   └── parser.py           # Navigation parsing
│   ├── modules/
│   │   ├── base.py             # Abstract base class
│   │   ├── gemini/             # Gemini documentation module
│   │   └── fastmcp/            # FastMCP documentation module
│   └── rag/
│       ├── chunker.py          # Markdown-aware chunking
│       ├── embedder.py         # Ollama bge-m3 embeddings
│       ├── sqlite_store.py     # SQLite + sqlite-vec vector store
│       ├── search.py           # Hybrid search with RRF
│       ├── query_expander.py   # Multi-query expansion (LLM)
│       ├── reranker.py         # Cross-encoder reranking
│       └── index.py            # Indexing CLI
├── output/                     # Fetched documentation
│   ├── gemini/
│   └── fastmcp/
├── data/
│   └── docs.db                 # SQLite vector database
├── requirements.txt
└── README.md
```

## Adding New Documentation Sources

1. Create a new module in `src/modules/<name>/`:

```python
# src/modules/example/config.py
BASE_URL = "https://docs.example.com"
SITEMAP_URL = "https://docs.example.com/sitemap.xml"
MARKDOWN_SUFFIX = ".md"  # or ".md.txt" for Google sites
```

```python
# src/modules/example/module.py
from src.modules.base import BaseModule

class ExampleModule(BaseModule):
    @property
    def name(self) -> str:
        return "example"

    def get_doc_urls(self) -> list[NavLink]:
        # Parse sitemap or navigation
        ...

    def fetch_page(self, url: str) -> str:
        # Fetch markdown content
        ...
```

2. Register in `src/main.py`:

```python
from src.modules.example.module import ExampleModule

# In fetch_command():
elif args.module == "example":
    module = ExampleModule()
    module.run(output_dir)
```

3. Add to `KNOWN_COLLECTIONS` in `src/mcp_server.py`

4. Fetch and index:

```bash
python -m src.main fetch example
python -m src.rag.index example
```

## How It Works

### Fetching
1. Parse navigation/sitemap to discover documentation pages
2. Fetch each page in markdown format (using source-specific tricks like `.md.txt` suffix)
3. Save with source URL metadata

### Indexing
1. Chunk markdown by headers (preserving code blocks)
2. Generate embeddings via Ollama bge-m3 (1024 dimensions)
3. Store in SQLite with sqlite-vec (vectors) and FTS5 (keywords)

### Searching
1. Generate query embedding
2. Perform semantic search (sqlite-vec vector similarity)
3. Perform keyword search (FTS5 BM25)
4. Combine with Reciprocal Rank Fusion (RRF)
5. Optionally expand query with LLM variations
6. Optionally rerank with cross-encoder
7. Return ranked results with source URLs

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |

### SQLite Database

Vector database stored in `data/docs.db`. Each documentation source gets its own collection within the database.

## Development

```bash
# Run tests
python -m pytest

# Check MCP server
claude mcp list

# Test search functionality
python -m src.rag.search
```

## Troubleshooting

### "Ollama connection failed"
```bash
# Make sure Ollama is running
ollama serve

# Pull the embedding model
ollama pull bge-m3
```

### "No results found"
```bash
# Check if collection is indexed
python -m src.rag.index --status gemini

# Re-index if needed
python -m src.rag.index --clear gemini
```

### MCP server not connecting
```bash
# Check server status
claude mcp list

# Reinstall
claude mcp remove docs-search
fastmcp install claude-code src/mcp_server.py --name docs-search
```

## License

MIT

## Credits

- [Ollama](https://ollama.ai/) - Local LLM and embeddings
- [sqlite-vec](https://github.com/asg017/sqlite-vec) - Vector search for SQLite
- [FastMCP](https://gofastmcp.com/) - MCP server framework
