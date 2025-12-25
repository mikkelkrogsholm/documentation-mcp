"""React Email documentation module implementation."""

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import html2text
import requests
from bs4 import BeautifulSoup

from src.core.parser import NavLink
from src.modules.base import BaseModule
from src.modules.reactemail import config


class ReactEmailModule(BaseModule):
    """Fetches React Email documentation from react.email/docs."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DocumentationFetcher/1.0"
        })
        self.delay = 0.5  # Rate limiting
        self._last_request_time = None

        # Configure html2text
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = False
        self.html_converter.ignore_emphasis = False
        self.html_converter.body_width = 0  # Don't wrap lines
        self.html_converter.protect_links = True
        self.html_converter.unicode_snob = True

    @property
    def name(self) -> str:
        return "reactemail"

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def get_doc_urls(self) -> list[NavLink]:
        """Parse sitemap to get all documentation URLs."""
        print(f"Fetching sitemap from {config.SITEMAP_URL}...")

        response = self.session.get(config.SITEMAP_URL, timeout=30)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Namespace handling for sitemap XML
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        links = []
        for url_elem in root.findall(".//sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            if loc is not None and loc.text:
                url = loc.text

                # Extract title from URL path
                parsed = urlparse(url)
                path = parsed.path.strip("/")
                segments = path.split("/")

                # Get the last segment as title
                title = segments[-1].replace("-", " ").replace("_", " ").title()

                # Handle special cases
                if title == "Docs" or not title:
                    title = "Introduction"

                # Calculate depth (relative to /docs/)
                # /docs/introduction = 0, /docs/components/button = 1
                depth = len(segments) - 2  # -2 for "docs" and the page
                depth = max(0, depth)

                links.append(NavLink(title=title, url=url, depth=depth))

        print(f"Found {len(links)} documentation pages")
        return links

    def _extract_content(self, html: str) -> str:
        """Extract main content from HTML page."""
        soup = BeautifulSoup(html, "lxml")

        # Remove unwanted elements first
        for selector in config.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        # Try to find main content area
        content = None
        for selector in config.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                break

        # Fallback to body if no content area found
        if not content:
            content = soup.body or soup

        return str(content)

    def fetch_page(self, url: str) -> str:
        """Fetch a single page and convert to markdown."""
        self._rate_limit()

        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        # Extract main content
        html_content = self._extract_content(response.text)

        # Convert to markdown
        markdown = self.html_converter.handle(html_content)

        # Clean up excessive whitespace
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        return markdown.strip()

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to a safe filename."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Remove docs/ prefix
        if path.startswith("docs/"):
            path = path[5:]

        # Handle empty path (index)
        if not path or path == "docs":
            path = "introduction"

        # Replace slashes with dashes
        filename = path.replace("/", "-")

        # Ensure .md extension
        if not filename.endswith(".md"):
            filename += ".md"

        return filename

    def run(self, output_dir: Path) -> None:
        """Fetch all documentation and save to output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get all documentation URLs
        links = self.get_doc_urls()

        if not links:
            print("No documentation pages found!")
            return

        # Fetch each page
        fetched_pages: list[tuple[NavLink, str]] = []

        for i, link in enumerate(links, 1):
            print(f"[{i}/{len(links)}] Fetching: {link.title}")
            try:
                content = self.fetch_page(link.url)
                if content:
                    fetched_pages.append((link, content))
                else:
                    print(f"  Warning: Empty content for {link.url}")
            except Exception as e:
                print(f"  Error fetching {link.url}: {e}")

        # Save each page
        print(f"\nSaving {len(fetched_pages)} pages to {output_dir}...")

        for link, content in fetched_pages:
            filename = self._url_to_filename(link.url)
            filepath = output_dir / filename

            # Prepend source URL comment
            full_content = f"<!-- Source: {link.url} -->\n\n{content}"

            filepath.write_text(full_content, encoding="utf-8")
            print(f"  Saved: {filename}")

        # Generate index
        self._generate_index(output_dir, fetched_pages)

        print(f"\nDone! Fetched {len(fetched_pages)} pages to {output_dir}")

    def _generate_index(
        self,
        output_dir: Path,
        pages: list[tuple[NavLink, str]]
    ) -> None:
        """Generate _index.md with hierarchical listing."""
        lines = [
            "# React Email Documentation",
            "",
            f"Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Total pages: {len(pages)}",
            "",
            "## Pages",
            "",
        ]

        for link, _ in pages:
            filename = self._url_to_filename(link.url)
            indent = "  " * link.depth
            lines.append(f"{indent}- [{link.title}]({filename})")

        index_path = output_dir / "_index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Saved: _index.md")
