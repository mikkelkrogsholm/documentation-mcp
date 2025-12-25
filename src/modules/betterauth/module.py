"""Better Auth documentation module implementation."""

import re
from datetime import datetime
from pathlib import Path

import requests

from src.core.parser import NavLink
from src.modules.base import BaseModule
from src.modules.betterauth import config


class BetterAuthModule(BaseModule):
    """Fetches Better Auth documentation from better-auth.com/llms.txt."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DocumentationFetcher/1.0"
        })

    @property
    def name(self) -> str:
        return "betterauth"

    def get_doc_urls(self) -> list[NavLink]:
        """Parse llms.txt to get all documentation URLs."""
        print(f"Fetching llms.txt from {config.LLMS_TXT_URL}...")

        response = self.session.get(config.LLMS_TXT_URL, timeout=30)
        response.raise_for_status()

        content = response.text

        # Extract all .md links from llms.txt
        # Pattern matches paths like /llms.txt/docs/introduction.md
        pattern = r"(/llms\.txt/docs/[^\s\)]+\.md)"
        matches = re.findall(pattern, content)

        links = []
        for path in matches:
            url = f"{config.BASE_URL}{path}"

            # Extract title from path
            # e.g., /llms.txt/docs/plugins/2fa.md -> "2fa"
            filename = path.split("/")[-1].replace(".md", "")
            title = filename.replace("-", " ").replace("_", " ").title()

            # Calculate depth from path structure
            # Remove /llms.txt/docs/ prefix and count remaining segments
            relative_path = path.replace("/llms.txt/docs/", "")
            segments = relative_path.split("/")
            depth = len(segments) - 1  # -1 because last segment is filename

            links.append(NavLink(title=title, url=url, depth=depth))

        print(f"Found {len(links)} documentation pages")
        return links

    def fetch_page(self, url: str) -> str:
        """Fetch a single page as markdown."""
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to a safe filename."""
        # Extract path after /llms.txt/docs/
        path = url.replace(f"{config.BASE_URL}/llms.txt/docs/", "")

        # Replace slashes with dashes
        filename = path.replace("/", "-")

        # Ensure .md extension (should already have it)
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
            "# Better Auth Documentation",
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
