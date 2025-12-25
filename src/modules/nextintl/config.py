"""next-intl documentation configuration."""

# Base URL for next-intl website
BASE_URL = "https://next-intl.dev"

# Sitemap URL
SITEMAP_URL = "https://next-intl.dev/sitemap-0.xml"

# Only fetch docs pages (filter pattern)
DOCS_PATH_PREFIX = "/docs/"

# CSS selectors for extracting main content (in priority order)
CONTENT_SELECTORS = [
    "article",
    "main article",
    "[data-docs-content]",
    ".docs-content",
    "main",
]

# Elements to remove from extracted content
REMOVE_SELECTORS = [
    "nav",
    "header",
    "footer",
    "aside",
    ".sidebar",
    ".toc",
    ".table-of-contents",
    ".breadcrumb",
    "script",
    "style",
    ".edit-on-github",
    ".page-navigation",
    "[aria-label='breadcrumb']",
]
