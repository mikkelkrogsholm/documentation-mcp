"""Drizzle ORM documentation configuration."""

# Base URL for Drizzle ORM website
BASE_URL = "https://orm.drizzle.team"

# URL for llms.txt which contains all documentation links
LLMS_TXT_URL = "https://orm.drizzle.team/llms.txt"

# CSS selectors for extracting main content from HTML pages
# These target the main documentation content area
CONTENT_SELECTORS = [
    "article",
    "main",
    ".docs-content",
    ".content",
    "[data-docs-content]",
]

# Elements to remove from extracted content (navigation, ads, etc.)
REMOVE_SELECTORS = [
    "nav",
    "header",
    "footer",
    ".sidebar",
    ".toc",
    ".table-of-contents",
    "script",
    "style",
    ".ads",
    ".banner",
]
