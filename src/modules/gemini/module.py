"""Gemini documentation module implementation."""

import re
from datetime import datetime
from pathlib import Path

from src.core.fetcher import Fetcher
from src.core.parser import NavLink, parse_nav_links
from src.modules.base import BaseModule
from src.modules.gemini import config


class GeminiModule(BaseModule):
    """Fetches Gemini API documentation."""

    def __init__(self):
        self.fetcher = Fetcher(delay=1.0)

    @property
    def name(self) -> str:
        return "gemini"

    def get_doc_urls(self) -> list[NavLink]:
        """Parse navigation to get all documentation URLs."""
        print(f"Fetching navigation from {config.BASE_URL}...")
        html = self.fetcher.fetch_html(config.BASE_URL)

        links = parse_nav_links(
            html=html,
            nav_selector=config.NAV_SELECTOR,
            base_url=config.BASE_URL,
            url_filter=config.URL_FILTER
        )

        print(f"Found {len(links)} documentation pages")
        return links

    def fetch_page(self, url: str) -> str:
        """Fetch a single page as markdown."""
        return self.fetcher.fetch_markdown(url, suffix=config.MARKDOWN_SUFFIX)

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to a safe filename."""
        # Extract path after /docs/
        match = re.search(r"/gemini-api/docs/?(.*?)(?:\?|#|$)", url)
        if match:
            path = match.group(1)
        else:
            path = url.split("/")[-1]

        # Handle empty path (main docs page)
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
        """Generate index.md with hierarchical listing."""
        lines = [
            "# Gemini API Documentation",
            "",
            f"Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Total pages: {len(pages)}",
            "",
            "## Pages",
            "",
        ]

        current_depth = 0
        for link, _ in pages:
            filename = self._url_to_filename(link.url)
            indent = "  " * link.depth
            lines.append(f"{indent}- [{link.title}]({filename})")

        index_path = output_dir / "index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Saved: index.md")
