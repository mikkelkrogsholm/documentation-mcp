"""FastMCP documentation module implementation."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from src.core.fetcher import Fetcher
from src.core.parser import NavLink
from src.modules.base import BaseModule
from src.modules.fastmcp import config


class FastMCPModule(BaseModule):
    """Fetches FastMCP documentation from gofastmcp.com."""

    def __init__(self):
        self.fetcher = Fetcher(delay=0.5)  # Faster since it's a docs site

    @property
    def name(self) -> str:
        return "fastmcp"

    def get_doc_urls(self) -> list[NavLink]:
        """Parse sitemap to get all documentation URLs."""
        print(f"Fetching sitemap from {config.SITEMAP_URL}...")

        # Fetch sitemap XML
        import requests
        response = requests.get(config.SITEMAP_URL, timeout=30)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Extract URLs from sitemap
        # Namespace handling for sitemap XML
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        links = []
        for url_elem in root.findall(".//sm:url", ns):
            loc = url_elem.find("sm:loc", ns)
            if loc is not None and loc.text:
                url = loc.text

                # Skip SDK reference pages if configured
                if config.SKIP_SDK_REFERENCE and "/python-sdk/" in url:
                    continue

                # Extract title from URL path
                path = url.replace(config.BASE_URL, "").strip("/")
                if not path:
                    title = "Home"
                else:
                    # Convert path to title: "getting-started/welcome" -> "Welcome"
                    title = path.split("/")[-1].replace("-", " ").title()

                # Calculate depth from path
                depth = len(path.split("/")) - 1 if path else 0

                links.append(NavLink(title=title, url=url, depth=depth))

        print(f"Found {len(links)} documentation pages")
        return links

    def fetch_page(self, url: str) -> str:
        """Fetch a single page as markdown."""
        return self.fetcher.fetch_markdown(url, suffix=config.MARKDOWN_SUFFIX)

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to a safe filename."""
        # Extract path after base URL
        path = url.replace(config.BASE_URL, "").strip("/")

        # Handle empty path (home page)
        if not path:
            path = "index"

        # Replace slashes with dashes, clean up
        filename = path.replace("/", "-").strip("-")

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
            "# FastMCP Documentation",
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
