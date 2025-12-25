"""Stripe documentation fetcher module."""

import re
import time
from pathlib import Path

import requests

from src.modules.base import BaseModule, NavLink
from src.modules.stripe import config


class StripeModule(BaseModule):
    """Fetches Stripe documentation from llms.txt with direct .md links."""

    @property
    def name(self) -> str:
        return "stripe"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; DocFetcher/1.0)"
        })

    def get_doc_urls(self) -> list[NavLink]:
        """Parse llms.txt to get all documentation URLs."""
        response = self.session.get(config.LLMS_TXT_URL, timeout=30)
        response.raise_for_status()
        content = response.text

        # Extract markdown links: [title](url)
        # Pattern matches [any text](https://docs.stripe.com/...\.md)
        pattern = r'\[([^\]]+)\]\((https://docs\.stripe\.com/[^\s\)]+\.md)\)'
        matches = re.findall(pattern, content)

        links = []
        seen_urls = set()

        for title, url in matches:
            if url not in seen_urls:
                seen_urls.add(url)
                links.append(NavLink(title=title.strip(), url=url))

        return links

    def fetch_page(self, url: str) -> str:
        """Fetch a documentation page - URLs already point to .md files."""
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def run(self, output_dir: str | Path) -> None:
        """Fetch all Stripe documentation."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"Fetching Stripe documentation to {output_path}")

        # Get all doc URLs
        print("Parsing llms.txt for documentation links...")
        links = self.get_doc_urls()
        print(f"Found {len(links)} documentation pages")

        # Fetch each page
        successful = 0
        failed = 0
        index_entries = []

        for i, link in enumerate(links, 1):
            # Generate filename from URL path
            # e.g., https://docs.stripe.com/payments/checkout.md -> payments-checkout.md
            url_path = link.url.replace(config.BASE_URL + "/", "")
            filename = url_path.replace("/", "-")
            if not filename.endswith(".md"):
                filename += ".md"

            filepath = output_path / filename

            try:
                print(f"  [{i}/{len(links)}] {link.title[:50]}...")
                content = self.fetch_page(link.url)

                # Add source URL as comment at top
                content_with_source = f"<!-- Source: {link.url} -->\n\n{content}"

                filepath.write_text(content_with_source, encoding="utf-8")
                successful += 1
                index_entries.append((link.title, filename, link.url))

                time.sleep(config.REQUEST_DELAY)

            except Exception as e:
                print(f"    Error: {e}")
                failed += 1

        # Write index file
        index_path = output_path / "_index.md"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("# Stripe Documentation\n\n")
            f.write(f"Fetched: {time.strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(f"Total pages: {successful}\n\n")
            f.write("## Pages\n\n")
            for title, filename, url in sorted(index_entries, key=lambda x: x[0].lower()):
                f.write(f"- [{title}]({filename})\n")

        print(f"\nComplete! {successful} pages fetched, {failed} failed")
        print(f"Output: {output_path}")
