"""Base HTTP/markdown fetching logic."""

import time
import requests
from typing import Optional


class Fetcher:
    """HTTP fetcher with rate limiting and retry logic."""

    def __init__(self, delay: float = 1.0, max_retries: int = 3):
        self.delay = delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DocumentationFetcher/1.0 (https://github.com/documentation-fetcher)"
        })
        self._last_request_time: Optional[float] = None

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def fetch_html(self, url: str) -> str:
        """Fetch HTML content from a URL."""
        self._rate_limit()

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                print(f"Retry {attempt + 1}/{self.max_retries} for {url}: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff

        return ""

    def fetch_markdown(self, url: str, suffix: str = ".md.txt") -> str:
        """Fetch markdown content by appending suffix to URL."""
        markdown_url = url.rstrip("/") + suffix
        return self.fetch_html(markdown_url)
