"""PDF extraction.

Two libraries, each used for what it is best at:

* PyMuPDF   - text, layout, font sizes, metadata and reading order (very fast).
* pdfplumber - table detection, which is far more accurate than plain text runs.

Text that falls inside a detected table is dropped from the prose blocks so the
same content is not stored twice.
"""

from __future__ import annotations

import io
import logging
import re
from collections import Counter

import pdfplumber
import pymupdf

from database.models import BlockType
from helper.extraction_models import (
    ExtractedBlock,
    ExtractedDocument,
    ExtractedTable,
    rows_to_markdown,
)

logger = logging.getLogger(__name__)
# pdfminer warns about every malformed font descriptor it meets; not actionable.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

_BOLD_FLAG = 1 << 4  # PyMuPDF span flag
_LIST_RE = re.compile(r"^\s*(?:[-•▪◦‣*·]|\(?\d{1,3}[.)]|\(?[a-zA-Z][.)])\s+")
_WHITESPACE_RE = re.compile(r"\s+")

# Fraction of the page height treated as the header / footer band.
_MARGIN_BAND = 0.08
# A page with less text than this is almost certainly a scan.
_OCR_TEXT_THRESHOLD = 20

# Fallbacks for half-ruled tables (only column rules, or only row rules).
# Both still require real ruling lines: a pure text/text strategy happily turns
# ordinary paragraphs into shredded "tables", which corrupts the extracted prose.
_PARTIAL_RULE_SETTINGS = (
    {"vertical_strategy": "lines", "horizontal_strategy": "text"},
    {"vertical_strategy": "text", "horizontal_strategy": "lines"},
)

# Pre-filter thresholds for `_has_table_rules`.
# Rules on one axis are enough, because the partial strategies above need only
# one. Two is the floor a genuine table can reach - a two-column table ruled
# down the columns alone - so raising this trades tables for seconds. Measured
# on a 340-page book: 2 admits 100 pages and finds every table, 5 admits 33 and
# loses one.
_MIN_RULES = 2
# A segment thinner than this is a rule; thicker on both axes makes it a box.
_RULE_TOLERANCE = 2.0
# A box this close to the page size is a background panel, not a table cell.
_FULL_PAGE_RATIO = 0.95


def extract_pdf(data: bytes) -> ExtractedDocument:
    """Extract text, structure, tables and metadata from PDF bytes."""
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.needs_pass:
            raise ValueError("The PDF is password protected and cannot be read.")

        # One pass: the text of every page, and which pages could hold a table.
        pages = []
        ruled_pages: set[int] = set()
        for page_no, page in enumerate(doc, start=1):
            pages.append(_page_blocks(page))
            if _has_table_rules(page):
                ruled_pages.add(page_no)

        metadata = _metadata(doc)
        page_count = doc.page_count

    tables_by_page = _extract_tables(data, ruled_pages)

    body_size = _body_font_size(pages)
    repeated = _repeated_margin_texts(pages)

    result = ExtractedDocument(metadata=metadata, page_count=page_count)
    table_counter = 0

    for page_no, page in enumerate(pages, start=1):
        page_tables = tables_by_page.get(page_no, [])
        text_blocks = _drop_blocks_inside_tables(page["blocks"], page_tables)

        # Interleave prose and tables by vertical position to keep reading order.
        items: list[tuple[float, float, str, object]] = [
            (b["bbox"][1], b["bbox"][0], "text", b) for b in text_blocks
        ]
        items += [(bbox[1], bbox[0], "table", rows) for bbox, rows in page_tables]
        items.sort(key=lambda item: (round(item[0], 1), item[1]))

        # (block, bbox) pairs; tables have no bbox because they never merge.
        entries: list[tuple[ExtractedBlock, tuple | None]] = []
        for _, _, kind, payload in items:
            if kind == "table":
                table = ExtractedTable(
                    page_number=page_no,
                    table_index=table_counter,
                    rows=payload,
                    markdown=rows_to_markdown(payload),
                )
                result.tables.append(table)
                entries.append(
                    (
                        ExtractedBlock(
                            page_number=page_no,
                            block_type=BlockType.TABLE,
                            content=table.markdown,
                            table_index=table_counter,
                            meta={"rows": table.n_rows, "columns": table.n_cols},
                        ),
                        None,
                    )
                )
                table_counter += 1
                continue

            block = _classify_block(payload, page_no, page["height"], body_size, repeated)
            if block is not None:
                entries.append((block, payload["bbox"]))

        page_blocks = _merge_paragraphs(entries)
        result.blocks.extend(page_blocks)

        page_chars = sum(len(block.content) for block in page_blocks)
        if page_chars < _OCR_TEXT_THRESHOLD:
            result.ocr_required_pages.append(page_no)

    return result


# --------------------------------------------------------------------------- #
# Tables (pdfplumber)
# --------------------------------------------------------------------------- #


def _extract_tables(
    data: bytes, pages: set[int]
) -> dict[int, list[tuple[tuple, list[list[str]]]]]:
    """Return {page_number: [(bbox, rows), ...]} for the given pages only."""
    found: dict[int, list[tuple[tuple, list[list[str]]]]] = {}
    if not pages:
        return found

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                if page_no not in pages:
                    continue  # no ruling lines: nothing here to find
                tables = _page_tables(page)
                if tables:
                    found[page_no] = tables
                page.flush_cache()  # pdfplumber caches every char per page
    except Exception:
        logger.warning("Table detection failed; continuing with text only.", exc_info=True)
    return found


def _rule_contribution(item, width: float, height: float) -> tuple[int, int]:
    """How many horizontal / vertical rules one drawing item is worth."""
    op = item[0]
    if op == "l":  # line: two points
        (x0, y0), (x1, y1) = item[1], item[2]
    elif op == "re":  # rectangle: (x0, y0, x1, y1)
        x0, y0, x1, y1 = item[1]
        if abs(x1 - x0) > _RULE_TOLERANCE and abs(y1 - y0) > _RULE_TOLERANCE:
            # A closed box is two rules per axis, unless it covers the page -
            # then it is a background panel and says nothing about tables.
            if (
                abs(x1 - x0) < width * _FULL_PAGE_RATIO
                or abs(y1 - y0) < height * _FULL_PAGE_RATIO
            ):
                return 2, 2
            return 0, 0
    else:  # curves and quads are never table rules
        return 0, 0

    if abs(y1 - y0) <= _RULE_TOLERANCE < abs(x1 - x0):
        return 1, 0
    if abs(x1 - x0) <= _RULE_TOLERANCE < abs(y1 - y0):
        return 0, 1
    return 0, 0


def _has_table_rules(page) -> bool:
    """Whether this page is worth handing to pdfplumber.

    pdfplumber reads every character on a page to find tables - around 120ms
    each, which is most of a minute on a long document that has almost no
    tables. Vector drawings are two orders of magnitude cheaper to read, and
    every strategy in `_page_tables` keys off ruling lines, so a page without
    them cannot yield a table however long we look at it.

    Deliberately generous: it errs towards saying yes, because a false yes only
    costs time while a false no silently loses a table.
    """
    try:
        paths = page.get_cdrawings()  # dicts, not Point/Rect objects: faster
    except Exception:
        return True  # unreadable drawings: let pdfplumber decide

    horizontal = vertical = 0
    width, height = page.rect.width, page.rect.height

    for path in paths:
        for item in path.get("items", ()):
            try:
                added_h, added_v = _rule_contribution(item, width, height)
            except (TypeError, ValueError, IndexError):
                continue  # an item shape we do not recognise
            horizontal += added_h
            vertical += added_v
            if horizontal >= _MIN_RULES or vertical >= _MIN_RULES:
                return True
    return False


def _page_tables(page) -> list[tuple[tuple, list[list[str]]]]:
    tables: list[tuple[tuple, list[list[str]]]] = []
    try:
        detected = page.find_tables()
    except Exception:
        detected = []

    for table in detected:
        rows = _clean_rows(table.extract())
        if rows:
            tables.append((table.bbox, rows))

    if tables:
        return tables

    # Nothing fully ruled: retry for tables that only rule one axis.
    for settings in _PARTIAL_RULE_SETTINGS:
        try:
            candidates = page.find_tables(settings)
        except Exception:
            continue
        for table in candidates:
            rows = _clean_rows(table.extract())
            if rows and _looks_like_table(rows):
                tables.append((table.bbox, rows))
        if tables:
            break
    return tables


def _clean_rows(rows) -> list[list[str]]:
    cleaned = [
        [_WHITESPACE_RE.sub(" ", (cell or "").replace("\n", " ")).strip() for cell in row]
        for row in rows or []
    ]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    return cleaned if len(cleaned) >= 2 else []


def _looks_like_table(rows: list[list[str]]) -> bool:
    """Guard the half-ruled strategies against picking up ordinary paragraphs.

    A real table is rectangular: nearly every row fills the same number of
    cells. Prose sliced into columns produces ragged rows instead.
    """
    if len(rows) < 3 or max(len(row) for row in rows) < 2:
        return False

    filled = Counter(sum(1 for cell in row if cell) for row in rows)
    width, matching = filled.most_common(1)[0]
    if width < 2 or matching < len(rows) * 0.8:
        return False

    cells = [cell for row in rows for cell in row if cell]
    return bool(cells) and sum(len(cell) for cell in cells) / len(cells) <= 60


def _drop_blocks_inside_tables(blocks: list[dict], tables: list[tuple]) -> list[dict]:
    """Remove prose that the table already captured, so nothing is stored twice.

    A block is only dropped when its text really is inside the table's cells:
    a table bbox often overlaps text the table itself did not pick up, and
    dropping that on position alone silently loses content.
    """
    if not tables:
        return blocks

    boxes = [(bbox, _squash(" ".join(cell for row in rows for cell in row)))
             for bbox, rows in tables]

    kept = []
    for block in blocks:
        text = _squash(_join_lines(block["lines"]))
        captured = any(
            _inside(block["bbox"], bbox) and text and text in table_text
            for bbox, table_text in boxes
        )
        if not captured:
            kept.append(block)
    return kept


def _squash(text: str) -> str:
    """Letters and digits only - lets text be compared across cell boundaries."""
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def _inside(bbox, box) -> bool:
    """True when the centre of `bbox` sits within `box` (both top-left origin)."""
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


# --------------------------------------------------------------------------- #
# Text and structure (PyMuPDF)
# --------------------------------------------------------------------------- #


def _page_blocks(page) -> dict:
    """Collect the text blocks of one page with the font info used for typing."""
    blocks: list[dict] = []
    for raw in page.get_text("dict", sort=True).get("blocks", []):
        if raw.get("type") != 0:  # 1 == image
            continue

        lines = []
        for line in raw.get("lines", []):
            spans = [s for s in line.get("spans", []) if s["text"].strip()]
            if not spans:
                continue
            lines.append(
                {
                    "text": "".join(span["text"] for span in line["spans"]),
                    "size": max(span["size"] for span in spans),
                    "bold": any(span["flags"] & _BOLD_FLAG for span in spans),
                }
            )
        if lines:
            blocks.append({"lines": lines, "bbox": raw["bbox"]})

    return {"blocks": blocks, "height": page.rect.height}


def _body_font_size(pages: list[dict]) -> float:
    """The most common font size, weighted by characters - i.e. the body text."""
    counter: Counter[float] = Counter()
    for page in pages:
        for block in page["blocks"]:
            for line in block["lines"]:
                counter[round(line["size"], 1)] += len(line["text"].strip())
    return counter.most_common(1)[0][0] if counter else 11.0


def _repeated_margin_texts(pages: list[dict]) -> set[str]:
    """Text that recurs in the top/bottom margin of many pages: running heads."""
    if len(pages) < 3:
        return set()

    counter: Counter[str] = Counter()
    for page in pages:
        band = page["height"] * _MARGIN_BAND
        for block in page["blocks"]:
            top, bottom = block["bbox"][1], block["bbox"][3]
            if top <= band or bottom >= page["height"] - band:
                counter[_normalise(_join_lines(block["lines"]))] += 1

    threshold = max(2, int(len(pages) * 0.3))
    return {text for text, count in counter.items() if text and count >= threshold}


def _normalise(text: str) -> str:
    """Ignore the digits so `Page 3 of 40` matches `Page 4 of 40`."""
    return re.sub(r"\d+", "#", text.strip().lower())


def _join_lines(lines: list[dict]) -> str:
    out = ""
    for line in lines:
        out = _append(out, line["text"].strip())
    return _WHITESPACE_RE.sub(" ", out).strip()


def _append(left: str, right: str) -> str:
    if not right:
        return left
    if not left:
        return right
    if left.endswith("-") and not left.endswith("--"):
        return left[:-1] + right  # de-hyphenate a word split across lines
    return f"{left} {right}"


def _merge_paragraphs(
    entries: list[tuple[ExtractedBlock, tuple | None]],
) -> list[ExtractedBlock]:
    """Rejoin paragraphs that the PDF stored as one block per visual line.

    HTML-to-PDF generators do this constantly. Blocks are merged only when they
    are tightly stacked and share a font size, so real paragraph breaks survive.
    """
    blocks: list[ExtractedBlock] = []
    previous_bbox: tuple | None = None

    for block, bbox in entries:
        mergeable = (
            blocks
            and bbox is not None
            and previous_bbox is not None
            and block.block_type == BlockType.PARAGRAPH
            and blocks[-1].block_type == BlockType.PARAGRAPH
            and block.meta.get("font_size") == blocks[-1].meta.get("font_size")
            and bbox[1] - previous_bbox[3] <= 0.6 * (block.meta.get("font_size") or 11.0)
        )
        if mergeable:
            blocks[-1].content = _append(blocks[-1].content, block.content)
        else:
            blocks.append(block)
        previous_bbox = bbox

    return blocks


def _classify_block(
    block: dict,
    page_no: int,
    page_height: float,
    body_size: float,
    repeated: set[str],
) -> ExtractedBlock | None:
    lines = block["lines"]
    text = _join_lines(lines)
    if not text:
        return None

    band = page_height * _MARGIN_BAND
    top, bottom = block["bbox"][1], block["bbox"][3]
    if _normalise(text) in repeated:
        block_type = BlockType.HEADER if top <= band else BlockType.FOOTER
        return ExtractedBlock(page_number=page_no, block_type=block_type, content=text)
    if bottom >= page_height - band and re.fullmatch(r"[\d\s\-–/]{1,12}", text):
        return ExtractedBlock(page_number=page_no, block_type=BlockType.FOOTER, content=text)

    max_size = max(line["size"] for line in lines)
    ratio = max_size / body_size if body_size else 1.0
    all_bold = all(line["bold"] for line in lines)

    is_heading = len(text) <= 200 and (
        ratio >= 1.15
        or (all_bold and ratio >= 0.98 and len(text) <= 120 and not text.endswith("."))
    )
    if is_heading:
        level = 1 if ratio >= 1.6 else 2 if ratio >= 1.35 else 3 if ratio >= 1.15 else 4
        return ExtractedBlock(
            page_number=page_no,
            block_type=BlockType.HEADING,
            content=text,
            heading_level=level,
            meta={"font_size": round(max_size, 1), "bold": all_bold},
        )

    block_type = BlockType.LIST_ITEM if _LIST_RE.match(text) else BlockType.PARAGRAPH
    return ExtractedBlock(
        page_number=page_no,
        block_type=block_type,
        content=text,
        meta={"font_size": round(max_size, 1)},
    )


def _metadata(doc) -> dict:
    meta = {key: value for key, value in (doc.metadata or {}).items() if value}
    try:
        toc = doc.get_toc()
        if toc:
            meta["toc"] = [
                {"level": level, "title": title, "page": page} for level, title, page in toc
            ]
    except Exception:
        pass
    return meta
