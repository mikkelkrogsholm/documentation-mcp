"""Abstract base class for documentation modules."""

from abc import ABC, abstractmethod
from pathlib import Path

from src.core.parser import NavLink


class BaseModule(ABC):
    """Base class that all documentation modules must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Module name (e.g., 'gemini', 'openai')."""
        pass

    @abstractmethod
    def get_doc_urls(self) -> list[NavLink]:
        """Discover and return all documentation page URLs."""
        pass

    @abstractmethod
    def fetch_page(self, url: str) -> str:
        """Fetch a single documentation page as markdown."""
        pass

    @abstractmethod
    def run(self, output_dir: Path) -> None:
        """
        Run the full documentation fetch process.

        Args:
            output_dir: Directory to save fetched documentation
        """
        pass
