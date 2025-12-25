"""Svelte documentation module implementation.

Fetches the complete Svelte/SvelteKit documentation from a single file
and splits it into sections for indexing.
"""

import re
from datetime import datetime
from pathlib import Path

import requests

from src.core.parser import NavLink
from src.modules.base import BaseModule
from src.modules.svelte import config


class SvelteModule(BaseModule):
    """Fetches Svelte documentation from svelte.dev/llms-full.txt."""

    def __init__(self):
        self._content: str | None = None
        self._sections: list[dict] | None = None

    @property
    def name(self) -> str:
        return "svelte"

    def _fetch_full_docs(self) -> str:
        """Download the complete documentation file."""
        if self._content is None:
            print(f"Fetching documentation from {config.DOCS_URL}...")
            response = requests.get(config.DOCS_URL, timeout=60)
            response.raise_for_status()
            self._content = response.text
            print(f"Downloaded {len(self._content):,} bytes")
        return self._content

    def _parse_sections(self, content: str) -> list[dict]:
        """Parse the markdown content into sections based on # headers."""
        if self._sections is not None:
            return self._sections

        sections = []
        current_framework = "svelte"  # Track if we're in Svelte or SvelteKit docs

        # Split by top-level headers (# Title)
        # Match lines that start with "# " but not "## " or more
        pattern = r'^# (.+)$'

        # Find all # headers and their positions
        matches = list(re.finditer(pattern, content, re.MULTILINE))

        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.start()

            # Get content until next # header or end of file
            if i + 1 < len(matches):
                end = matches[i + 1].start()
            else:
                end = len(content)

            section_content = content[start:end].strip()

            # Track which framework we're documenting
            if "Start of Svelte documentation" in title:
                current_framework = "svelte"
                continue  # Skip the marker itself
            elif "Start of SvelteKit documentation" in title:
                current_framework = "kit"
                continue  # Skip the marker itself

            # Skip system/metadata sections
            if title.startswith("<") or "available-docs" in section_content[:100].lower():
                continue

            # Generate a slug from the title
            slug = self._title_to_slug(title)

            # Construct source URL
            if current_framework == "kit":
                source_url = f"https://svelte.dev/docs/kit/{slug}"
            else:
                source_url = f"https://svelte.dev/docs/svelte/{slug}"

            sections.append({
                "title": title,
                "slug": slug,
                "framework": current_framework,
                "content": section_content,
                "source_url": source_url,
            })

        self._sections = sections
        return sections

    def _title_to_slug(self, title: str) -> str:
        """Convert a section title to a URL-friendly slug."""
        # Handle special characters
        slug = title.lower()

        # Replace common patterns
        slug = slug.replace("$", "")  # $state -> state
        slug = slug.replace("{#", "").replace("}", "")  # {#if ...} -> if
        slug = slug.replace("{@", "").replace("}", "")  # {@html ...} -> html
        slug = slug.replace("{", "").replace("}", "")
        slug = slug.replace("...", "")
        slug = slug.replace("<", "").replace(">", "")
        slug = slug.replace(":", "-")

        # Replace spaces and special chars with hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', slug)

        # Clean up multiple hyphens and trim
        slug = re.sub(r'-+', '-', slug).strip('-')

        return slug or "index"

    def get_doc_urls(self) -> list[NavLink]:
        """Get all documentation section URLs."""
        content = self._fetch_full_docs()
        sections = self._parse_sections(content)

        print(f"Found {len(sections)} documentation sections")

        return [
            NavLink(
                title=f"[{s['framework']}] {s['title']}",
                url=s['source_url'],
                depth=0
            )
            for s in sections
        ]

    def fetch_page(self, url: str) -> str:
        """Fetch a single page - returns content from parsed sections."""
        content = self._fetch_full_docs()
        sections = self._parse_sections(content)

        for section in sections:
            if section['source_url'] == url:
                return section['content']

        return ""

    def run(self, output_dir: Path) -> None:
        """Fetch and save all documentation sections."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Fetch and parse
        content = self._fetch_full_docs()
        sections = self._parse_sections(content)

        if not sections:
            print("No sections found!")
            return

        print(f"\nSaving {len(sections)} sections to {output_dir}...")

        # Save each section
        saved_count = 0
        for section in sections:
            # Create filename: framework-slug.md
            filename = f"{section['framework']}-{section['slug']}.md"
            filepath = output_dir / filename

            # Add source URL comment
            full_content = f"<!-- Source: {section['source_url']} -->\n\n{section['content']}"

            filepath.write_text(full_content, encoding="utf-8")
            saved_count += 1

        print(f"Saved {saved_count} sections")

        # Generate index
        self._generate_index(output_dir, sections)

        print(f"\nDone! Fetched {saved_count} sections to {output_dir}")

    def _generate_index(self, output_dir: Path, sections: list[dict]) -> None:
        """Generate _index.md with listing."""
        # Group by framework
        svelte_sections = [s for s in sections if s['framework'] == 'svelte']
        kit_sections = [s for s in sections if s['framework'] == 'kit']

        lines = [
            "# Svelte Documentation",
            "",
            f"Fetched: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Total sections: {len(sections)}",
            f"- Svelte: {len(svelte_sections)} sections",
            f"- SvelteKit: {len(kit_sections)} sections",
            "",
            "## Svelte",
            "",
        ]

        for section in svelte_sections:
            filename = f"{section['framework']}-{section['slug']}.md"
            lines.append(f"- [{section['title']}]({filename})")

        lines.extend([
            "",
            "## SvelteKit",
            "",
        ])

        for section in kit_sections:
            filename = f"{section['framework']}-{section['slug']}.md"
            lines.append(f"- [{section['title']}]({filename})")

        index_path = output_dir / "_index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")
        print("Saved: _index.md")
