"""Parser-independent result types.

The PDF and DOCX extractors both produce an `ExtractedDocument`, so everything
downstream (chunking, persistence, retrieval) is written once.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from database.models import BlockType


@dataclass(slots=True)
class ExtractedBlock:
    """A piece of content in reading order."""

    page_number: int
    block_type: BlockType
    content: str
    heading_level: int | None = None
    meta: dict = field(default_factory=dict)
    # Set when the block is a table, so it can be linked to its table row.
    table_index: int | None = None


@dataclass(slots=True)
class ExtractedTable:
    page_number: int
    table_index: int
    rows: list[list[str]]
    markdown: str

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_cols(self) -> int:
        return max((len(row) for row in self.rows), default=0)


@dataclass(slots=True)
class ExtractedDocument:
    blocks: list[ExtractedBlock] = field(default_factory=list)
    tables: list[ExtractedTable] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    page_count: int = 0
    # Pages that yielded (almost) no text - most likely scans needing OCR.
    ocr_required_pages: list[int] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(block.content for block in self.blocks if block.content)

    @property
    def char_count(self) -> int:
        return sum(len(block.content) for block in self.blocks)

    @property
    def word_count(self) -> int:
        return sum(len(block.content.split()) for block in self.blocks)


def rows_to_markdown(rows: list[list[str]]) -> str:
    """Render table rows as a markdown table (the format LLMs read best)."""
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    padded = [
        [(cell or "").replace("|", "\\|").replace("\n", " ").strip() for cell in row]
        + [""] * (width - len(row))
        for row in rows
    ]

    header, *body = padded
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(lines)
