"""Resend documentation module implementation."""

import re
from datetime import datetime
from pathlib import Path

import requests

from src.core.parser import NavLink
from src.modules.base import BaseModule
from src.modules.resend import config


class ResendModule(BaseModule):
    """Fetches Resend documentation from a single llms-full.txt file."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DocumentationFetcher/1.0"
        })
        self._sections: list[tuple[str, str, str]] = []  # (title, source_url, content)

    @property
    def name(self) -> str:
        return "resend"

    def get_doc_urls(self) -> list[NavLink]:
        """Parse the full docs file and return section info as NavLinks."""
        print(f"Fetching full docs from {config.LLMS_FULL_URL}...")

        response = self.session.get(config.LLMS_FULL_URL, timeout=60)
        response.raise_for_status()

        content = response.text

        # Split on "# " at the start of a line
        # First section might not start with \n# so handle specially
        if content.startswith("# "):
            sections = content.split(config.SECTION_DELIMITER)
            # First element is empty or the first section without leading \n
            sections = ["# " + s for s in sections if s.strip()]
        else:
            parts = content.split(config.SECTION_DELIMITER)
            # First part is before any # header (preamble), rest are sections
            sections = ["# " + s for s in parts[1:] if s.strip()]

        links = []
        self._sections = []

        for section in sections:
            lines = section.split("\n")
            if not lines:
                continue

            # Extract title from first line (# Title)
            title_line = lines[0]
            title = title_line.lstrip("# ").strip()

            # Look for Source: URL in the next few lines
            source_url = ""
            for line in lines[1:5]:
                if line.startswith("Source:"):
                    source_url = line.replace("Source:", "").strip()
                    break

            if not source_url:
                source_url = f"{config.BASE_URL}/docs"

            # Store section for later
            self._sections.append((title, source_url, section))

            # Calculate depth based on URL structure
            depth = 0
            if "/api-reference/" in source_url:
                depth = 1
            elif "/sdk/" in source_url:
                depth = 1

            links.append(NavLink(title=title, url=source_url, depth=depth))

        print(f"Found {len(links)} documentation sections")
        return links

    def fetch_page(self, url: str) -> str:
        """Not used - content already loaded in get_doc_urls."""
        # Find the section by URL
        for title, source_url, content in self._sections:
            if source_url == url:
                return content
        return ""

    def _title_to_filename(self, title: str) -> str:
        """Convert title to a safe filename."""
        # Convert to lowercase, replace spaces with dashes
        filename = title.lower()
        filename = re.sub(r"[^a-z0-9\s-]", "", filename)
        filename = re.sub(r"\s+", "-", filename)
        filename = re.sub(r"-+", "-", filename)
        filename = filename.strip("-")

        # Ensure .md extension
        if not filename.endswith(".md"):
            filename += ".md"

        return filename

    def run(self, output_dir: Path) -> None:
        """Fetch all documentation and save to output directory."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get all documentation sections (this also populates self._sections)
        links = self.get_doc_urls()

        if not links or not self._sections:
            print("No documentation sections found!")
            return

        # Save each section
        print(f"\nSaving {len(self._sections)} sections to {output_dir}...")

        saved_pages: list[tuple[NavLink, str]] = []
        seen_filenames: dict[str, int] = {}

        for i, (title, source_url, content) in enumerate(self._sections):
            # Generate unique filename
            base_filename = self._title_to_filename(title)

            # Handle duplicates by adding a number suffix
            if base_filename in seen_filenames:
                seen_filenames[base_filename] += 1
                name_part = base_filename.rsplit(".", 1)[0]
                base_filename = f"{name_part}-{seen_filenames[base_filename]}.md"
            else:
                seen_filenames[base_filename] = 1

            filepath = output_dir / base_filename

            # Prepend source URL comment
            full_content = f"<!-- Source: {source_url} -->\n\n{content}"

            filepath.write_text(full_content, encoding="utf-8")
            print(f"  [{i+1}/{len(self._sections)}] Saved: {base_filename}")

            # Find corresponding NavLink
            link = links[i] if i < len(links) else NavLink(title=title, url=source_url, depth=0)
            saved_pages.append((link, content))

        # Generate index
        self._generate_index(output_dir, saved_pages, seen_filenames)

        print(f"\nDone! Saved {len(self._sections)} sections to {output_dir}")

    def _generate_index(
        self,
        output_dir: Path,
        pages: list[tuple[NavLink, str]],
        seen_filenames: dict[str, int]
    ) -> None:
        """Generate _index.md with listing."""
        lines = [
            "# Resend Documentation",
            "",
            f"Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Total sections: {len(pages)}",
            "",
            "## Sections",
            "",
        ]

        # Track filenames for proper linking
        filename_counts: dict[str, int] = {}

        for link, _ in pages:
            base_filename = self._title_to_filename(link.title)

            # Handle duplicates consistently with run()
            if base_filename in filename_counts:
                filename_counts[base_filename] += 1
                name_part = base_filename.rsplit(".", 1)[0]
                filename = f"{name_part}-{filename_counts[base_filename]}.md"
            else:
                filename_counts[base_filename] = 1
                filename = base_filename

            indent = "  " * link.depth
            lines.append(f"{indent}- [{link.title}]({filename})")

        index_path = output_dir / "_index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"  Saved: _index.md")
