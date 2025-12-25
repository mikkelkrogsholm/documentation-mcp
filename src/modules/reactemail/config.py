"""React Email documentation configuration."""

# Base URL for React Email docs
BASE_URL = "https://react.email"

# Sitemap URL for docs
SITEMAP_URL = "https://react.email/docs/sitemap.xml"

# CSS selectors for extracting main content (in priority order)
CONTENT_SELECTORS = [
    "article",
    "#content-area",
    "main article",
    "[data-docs-content]",
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
    "#sidebar",
    ".feedback",
    ".on-this-page",
]
