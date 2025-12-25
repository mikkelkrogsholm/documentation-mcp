"""shadcn/ui documentation module implementation."""

import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.core.parser import NavLink
from src.modules.base import BaseModule
from src.modules.shadcn import config


class ShadcnModule(BaseModule):
    """Fetches shadcn/ui documentation from ui.shadcn.com."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DocumentationFetcher/1.0"
        })
        self.delay = 0.3  # Rate limiting
        self._last_request_time = None

    @property
    def name(self) -> str:
        return "shadcn"

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def get_doc_urls(self) -> list[NavLink]:
        """Parse llms.txt to get all documentation URLs."""
        print(f"Fetching llms.txt from {config.LLMS_TXT_URL}...")

        response = self.session.get(config.LLMS_TXT_URL, timeout=30)
        response.raise_for_status()

        content = response.text

        # Extract all URLs from llms.txt
        # Pattern matches URLs starting with https://ui.shadcn.com/docs/
        pattern = r"(https://ui\.shadcn\.com/docs[^\s\)\"\'\,]+)"
        matches = re.findall(pattern, content)

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in matches:
            # Clean URL (remove trailing punctuation)
            url = url.rstrip(".,;:")
            # Skip schema URLs
            if "/schema/" in url:
                continue
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        links = []
        for url in unique_urls:
            # Extract title from URL path
            parsed = urlparse(url)
            path = parsed.path.strip("/")
            segments = path.split("/")

            # Get title from last segment
            title = segments[-1].replace("-", " ").replace("_", " ").title()

            # Handle index page
            if title == "Docs" or not title:
                title = "Introduction"

            # Calculate depth
            # /docs = 0, /docs/components/button = 1
            depth = len(segments) - 2  # -2 for "docs" and the page
            depth = max(0, depth)

            links.append(NavLink(title=title, url=url, depth=depth))

        print(f"Found {len(links)} documentation pages")
        return links

    def fetch_page(self, url: str) -> str:
        """Fetch a single page as markdown by appending .md suffix."""
        self._rate_limit()

        markdown_url = url.rstrip("/") + config.MARKDOWN_SUFFIX
        response = self.session.get(markdown_url, timeout=30)
        response.raise_for_status()

        return response.text

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to a safe filename."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        # Remove docs/ prefix
        if path.startswith("docs/"):
            path = path[5:]

        # Handle empty path
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
            "# shadcn/ui Documentation",
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
