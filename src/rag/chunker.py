"""Markdown-aware chunker for RAG applications.

Intelligently splits markdown documents into semantic chunks while:
- Preserving document structure (headers, code blocks)
- Maintaining optimal chunk sizes for embeddings
- Extracting rich metadata for retrieval
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Chunk:
    """Represents a semantic chunk of documentation with metadata."""

    content: str
    metadata: dict  # source_url, page_title, section, hierarchy, has_code


class MarkdownChunker:
    """Handles intelligent chunking of markdown documentation."""

    # Approximate tokens calculation: ~4 chars per token
    CHARS_PER_TOKEN = 4
    TARGET_MIN_TOKENS = 400
    TARGET_MAX_TOKENS = 500
    TARGET_MIN_CHARS = TARGET_MIN_TOKENS * CHARS_PER_TOKEN  # 1600
    TARGET_MAX_CHARS = TARGET_MAX_TOKENS * CHARS_PER_TOKEN  # 2000

    # Regex patterns
    SOURCE_PATTERN = re.compile(r'<!--\s*Source:\s*(.+?)\s*-->')
    H1_PATTERN = re.compile(r'^#\s+(.+)$', re.MULTILINE)
    HEADER_PATTERN = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)
    # Match both fenced code blocks (```) and indented code blocks (4+ spaces)
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```|(?:^|\n)(?: {4,}|\t).+(?:\n(?: {4,}|\t).+)*', re.MULTILINE)

    def __init__(self, filepath: Path):
        """Initialize chunker with a markdown file.

        Args:
            filepath: Path to the markdown file to chunk
        """
        self.filepath = filepath
        self.content = filepath.read_text(encoding='utf-8')
        self.source_url = self._extract_source_url()
        self.page_title = self._extract_page_title()

    def _extract_source_url(self) -> Optional[str]:
        """Extract source URL from <!-- Source: URL --> comment."""
        match = self.SOURCE_PATTERN.search(self.content)
        return match.group(1) if match else None

    def _extract_page_title(self) -> Optional[str]:
        """Extract page title from first # header."""
        match = self.H1_PATTERN.search(self.content)
        return match.group(1) if match else None

    def _has_code_blocks(self, text: str) -> bool:
        """Check if text contains code blocks."""
        return bool(self.CODE_BLOCK_PATTERN.search(text))

    def _find_code_block_ranges(self, text: str) -> list[tuple[int, int]]:
        """Find all code block positions in text.

        Returns:
            List of (start, end) tuples for each code block
        """
        ranges = []
        for match in self.CODE_BLOCK_PATTERN.finditer(text):
            ranges.append((match.start(), match.end()))
        return ranges

    def _is_inside_code_block(self, pos: int, code_ranges: list[tuple[int, int]]) -> bool:
        """Check if position is inside a code block."""
        return any(start <= pos < end for start, end in code_ranges)

    def _split_on_paragraphs(self, text: str, max_size: int) -> list[str]:
        """Split text on paragraph boundaries while respecting code blocks.

        Args:
            text: Text to split
            max_size: Maximum size in characters

        Returns:
            List of text chunks
        """
        if len(text) <= max_size:
            return [text]

        code_ranges = self._find_code_block_ranges(text)

        # Split on double newlines (paragraph boundaries)
        paragraphs = re.split(r'\n\n+', text)

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            # If adding this paragraph would exceed max size, save current chunk
            if current_chunk and current_size + para_size + 2 > max_size:  # +2 for \n\n
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0

            current_chunk.append(para)
            current_size += para_size + 2  # +2 for \n\n separator

        # Add remaining paragraphs
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks

    def _extract_hierarchy(self, section_header: Optional[str],
                          preceding_sections: list[str]) -> list[str]:
        """Build hierarchy list from preceding sections.

        Args:
            section_header: Current section header (e.g., "## Overview")
            preceding_sections: List of previous headers in document order

        Returns:
            Hierarchy list (e.g., ["Installation", "Prerequisites", "Overview"])
        """
        if not section_header:
            return []

        # Parse current header level
        match = re.match(r'^(#{2,3})\s+(.+)$', section_header)
        if not match:
            return []

        current_level = len(match.group(1))
        current_title = match.group(2)

        # Build hierarchy from preceding sections
        hierarchy = []
        for prev_header in preceding_sections:
            prev_match = re.match(r'^(#{2,3})\s+(.+)$', prev_header)
            if prev_match:
                prev_level = len(prev_match.group(1))
                prev_title = prev_match.group(2)

                # Only include headers at higher levels (fewer #s)
                if prev_level < current_level:
                    hierarchy.append(prev_title)

        # Add current section
        hierarchy.append(current_title)

        return hierarchy

    def chunk(self) -> list[Chunk]:
        """Chunk the markdown file into semantic pieces.

        Returns:
            List of Chunk objects with content and metadata
        """
        chunks = []

        # Remove source comment from content
        working_content = self.SOURCE_PATTERN.sub('', self.content).strip()

        # Find all ## and ### headers
        sections = []
        last_end = 0
        header_history = []

        # Track the introductory content before first header
        first_header_match = self.HEADER_PATTERN.search(working_content)
        if first_header_match:
            intro_content = working_content[:first_header_match.start()].strip()
            if intro_content:
                # Create chunk for intro (includes h1 title)
                sections.append({
                    'header': None,
                    'content': intro_content,
                    'start': 0,
                    'end': first_header_match.start(),
                    'hierarchy': []
                })
                last_end = first_header_match.start()

        # Find all section headers and their content
        for match in self.HEADER_PATTERN.finditer(working_content):
            if last_end < match.start():
                # There's content before this header that belongs to previous section
                # This is handled by the next section's start position
                pass

            # Find next header or end of document
            next_match = None
            for next_candidate in self.HEADER_PATTERN.finditer(working_content):
                if next_candidate.start() > match.start():
                    next_match = next_candidate
                    break

            section_end = next_match.start() if next_match else len(working_content)
            section_content = working_content[match.start():section_end].strip()
            header_text = match.group(0)

            hierarchy = self._extract_hierarchy(header_text, header_history)
            header_history.append(header_text)

            sections.append({
                'header': header_text,
                'content': section_content,
                'start': match.start(),
                'end': section_end,
                'hierarchy': hierarchy
            })

            last_end = section_end

        # If no sections found, treat entire document as one chunk
        if not sections:
            sections.append({
                'header': None,
                'content': working_content,
                'start': 0,
                'end': len(working_content),
                'hierarchy': []
            })

        # Process each section
        for section in sections:
            content = section['content']
            header = section['header']
            hierarchy = section['hierarchy']

            # Extract section title from header
            section_title = None
            if header:
                header_match = re.match(r'^#{2,3}\s+(.+)$', header)
                section_title = header_match.group(1) if header_match else None

            # If section is within target size, create single chunk
            if len(content) <= self.TARGET_MAX_CHARS:
                chunks.append(Chunk(
                    content=content,
                    metadata={
                        'source_url': self.source_url,
                        'page_title': self.page_title,
                        'section': section_title,
                        'hierarchy': hierarchy,
                        'has_code': self._has_code_blocks(content)
                    }
                ))
            else:
                # Section too large, split on paragraphs
                sub_chunks = self._split_on_paragraphs(content, self.TARGET_MAX_CHARS)

                for i, sub_content in enumerate(sub_chunks):
                    # For sub-chunks, indicate position in metadata
                    sub_section_title = section_title
                    if len(sub_chunks) > 1:
                        sub_section_title = f"{section_title} (part {i+1}/{len(sub_chunks)})" if section_title else f"Part {i+1}/{len(sub_chunks)}"

                    chunks.append(Chunk(
                        content=sub_content,
                        metadata={
                            'source_url': self.source_url,
                            'page_title': self.page_title,
                            'section': sub_section_title,
                            'hierarchy': hierarchy,
                            'has_code': self._has_code_blocks(sub_content)
                        }
                    ))

        return chunks


def chunk_markdown(filepath: Path) -> list[Chunk]:
    """Chunk a markdown file into semantic pieces.

    Extracts source_url from <!-- Source: URL --> comment at top.
    Extracts page_title from first # header.

    Args:
        filepath: Path to the markdown file

    Returns:
        List of Chunk objects containing content and metadata

    Example:
        >>> chunks = chunk_markdown(Path("output/gemini/function-calling.md"))
        >>> len(chunks)
        3
        >>> chunks[0].metadata['page_title']
        'Function Calling'
        >>> chunks[0].metadata['has_code']
        True
    """
    chunker = MarkdownChunker(filepath)
    return chunker.chunk()
