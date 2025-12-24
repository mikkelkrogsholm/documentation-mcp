"""Claude Code documentation module implementation."""

from datetime import datetime
from pathlib import Path

from src.core.fetcher import Fetcher
from src.core.parser import NavLink
from src.modules.base import BaseModule
from src.modules.claudecode import config


class ClaudeCodeModule(BaseModule):
    """Fetches Claude Code documentation from code.claude.com."""

    def __init__(self):
        self.fetcher = Fetcher(delay=0.5)

    @property
    def name(self) -> str:
        return "claudecode"

    def get_doc_urls(self) -> list[NavLink]:
        """Get all documentation URLs from config."""
        print(f"Loading {len(config.DOC_PAGES)} documentation pages...")

        links = []
        for title, slug in config.DOC_PAGES:
            url = f"{config.BASE_URL}/{slug}"
            # Calculate depth from slug (e.g., "hooks-guide" = 0, no hierarchy)
            depth = 0
            links.append(NavLink(title=title, url=url, depth=depth))

        print(f"Found {len(links)} documentation pages")
        return links

    def fetch_page(self, url: str) -> str:
        """Fetch a single page as markdown."""
        # Append .md to get raw markdown
        markdown_url = url + config.MARKDOWN_SUFFIX
        return self.fetcher.fetch_markdown(markdown_url, suffix="")

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to a safe filename."""
        # Extract slug from URL
        slug = url.replace(config.BASE_URL + "/", "").strip("/")

        # Handle empty slug
        if not slug:
            slug = "index"

        # Ensure .md extension
        if not slug.endswith(".md"):
            slug += ".md"

        return slug

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
        """Generate _index.md with listing."""
        lines = [
            "# Claude Code Documentation",
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
            lines.append(f"- [{link.title}]({filename})")

        index_path = output_dir / "_index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Saved: _index.md")
