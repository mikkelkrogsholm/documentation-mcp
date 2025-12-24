"""Base navigation parsing logic."""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup


@dataclass
class NavLink:
    """A navigation link with hierarchy information."""
    title: str
    url: str
    depth: int = 0


def parse_nav_links(
    html: str,
    nav_selector: str,
    base_url: str,
    link_selector: str = "a",
    url_filter: Optional[str] = None
) -> list[NavLink]:
    """
    Parse navigation links from HTML.

    Args:
        html: HTML content to parse
        nav_selector: CSS selector for the navigation container
        base_url: Base URL for resolving relative links
        link_selector: CSS selector for links within navigation
        url_filter: Only include URLs containing this string

    Returns:
        List of NavLink objects with title, URL, and depth
    """
    soup = BeautifulSoup(html, "lxml")
    nav = soup.select_one(nav_selector)

    if not nav:
        return []

    links: list[NavLink] = []
    seen_urls: set[str] = set()

    for anchor in nav.select(link_selector):
        href = anchor.get("href")
        if not href:
            continue

        # Resolve relative URLs
        full_url = urljoin(base_url, href)

        # Apply URL filter if specified
        if url_filter and url_filter not in full_url:
            continue

        # Skip duplicates
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Skip anchor links and external links
        if href.startswith("#") or href.startswith("mailto:"):
            continue

        # Get title from anchor text
        title = anchor.get_text(strip=True)
        if not title:
            continue

        # Calculate depth based on nesting (simplified)
        depth = len(anchor.find_parents("ul"))

        links.append(NavLink(title=title, url=full_url, depth=depth))

    return links
