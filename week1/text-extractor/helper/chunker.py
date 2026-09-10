"""Turn extracted blocks into retrieval chunks.

A chunk is what the question endpoint feeds to the LLM, so it has to stay
self-contained: it carries the heading it sits under and the pages it came from.
"""

from __future__ import annotations

from dataclasses import dataclass

from database.models import BlockType
from helper.extraction_models import ExtractedBlock

# Headers/footers are page furniture - they only add noise to retrieval.
_SKIPPED = {BlockType.HEADER, BlockType.FOOTER}
# Rough characters-per-token ratio for English text.
_CHARS_PER_TOKEN = 4


@dataclass(slots=True)
class Chunk:
    chunk_index: int
    content: str
    section_title: str | None
    page_start: int
    page_end: int

    @property
    def char_count(self) -> int:
        return len(self.content)

    @property
    def token_estimate(self) -> int:
        return max(1, len(self.content) // _CHARS_PER_TOKEN)


def build_chunks(
    blocks: list[ExtractedBlock], chunk_size: int, overlap: int
) -> list[Chunk]:
    builder = _ChunkBuilder(chunk_size, overlap)

    for block in blocks:
        if block.block_type in _SKIPPED or not block.content.strip():
            continue

        if block.block_type == BlockType.HEADING:
            # Start a new chunk so a section never begins mid-chunk.
            builder.flush()
            builder.section_title = block.content
            builder.add(block.content, block.page_number)
            continue

        if block.block_type == BlockType.TABLE and len(block.content) > chunk_size:
            builder.flush()
            for part in _split_table(block.content, chunk_size):
                builder.add(part, block.page_number)
                builder.flush(carry_overlap=False)
            continue

        builder.add(block.content, block.page_number)

    builder.flush()
    return builder.chunks


class _ChunkBuilder:
    def __init__(self, chunk_size: int, overlap: int) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: list[Chunk] = []
        self.section_title: str | None = None
        self._parts: list[str] = []
        self._length = 0
        self._page_start = 1
        self._page_end = 1

    def add(self, text: str, page: int) -> None:
        text = text.strip()
        if not text:
            return
        if self._parts and self._length + len(text) > self.chunk_size:
            self.flush()
        if not self._parts:
            self._page_start = page
            self._page_end = page
        self._parts.append(text)
        self._length += len(text) + 2
        self._page_end = max(self._page_end, page)

    def flush(self, carry_overlap: bool = True) -> None:
        if not self._parts:
            return

        content = "\n\n".join(self._parts).strip()
        self.chunks.append(
            Chunk(
                chunk_index=len(self.chunks),
                content=content,
                section_title=self.section_title,
                page_start=self._page_start,
                page_end=self._page_end,
            )
        )

        tail = _tail(content, self.overlap) if carry_overlap and self.overlap else ""
        self._parts = [tail] if tail else []
        self._length = len(tail)
        self._page_start = self._page_end


def _tail(text: str, overlap: int) -> str:
    """Last `overlap` characters, trimmed to a word boundary."""
    if len(text) <= overlap:
        return text
    tail = text[-overlap:]
    space = tail.find(" ")
    return tail[space + 1 :].strip() if space != -1 else tail.strip()


def _split_table(markdown: str, chunk_size: int) -> list[str]:
    """Split a long markdown table, repeating the header row in every part."""
    lines = markdown.splitlines()
    if len(lines) < 3:
        return [markdown]

    header = lines[:2]
    header_len = sum(len(line) + 1 for line in header)

    parts: list[str] = []
    current: list[str] = []
    length = header_len

    for line in lines[2:]:
        if current and length + len(line) + 1 > chunk_size:
            parts.append("\n".join(header + current))
            current, length = [], header_len
        current.append(line)
        length += len(line) + 1

    if current:
        parts.append("\n".join(header + current))
    return parts
