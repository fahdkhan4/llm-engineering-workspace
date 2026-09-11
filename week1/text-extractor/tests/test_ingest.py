"""Ingest pipeline tests.

Two changes these lock down, both made to cut a 340 page upload from ~75s:

* Table detection now runs only on pages that carry ruling lines, because
  pdfplumber reads every character on a page and that was most of the wait.
  The risk is a page being filtered out that did hold a table, so the
  assertions are about tables still coming out, not about speed.

* Chunk embeddings are batched in parallel and tolerated per batch. The
  risks are a scrambled or short result, and one failed batch taking the
  whole document down with it - which is what used to happen.
"""

from __future__ import annotations

import numpy as np
import pytest

from conftest import build_pdf


# --------------------------------------------------------------------------- #
# The table pre-filter
# --------------------------------------------------------------------------- #


def test_ruled_table_survives_the_page_filter(app_modules, tmp_path):
    """The whole point of the filter: it must not cost us a table."""
    from helper.pdf_extractor import extract_pdf

    extracted = extract_pdf(build_pdf(tmp_path / "table.pdf"))

    assert len(extracted.tables) == 1
    table = extracted.tables[0]
    assert table.page_number == 2
    assert "us-east" in table.markdown and "28ms" in table.markdown
    assert table.n_rows == 3 and table.n_cols == 3


def test_filter_skips_prose_and_admits_rules(app_modules, tmp_path):
    """The saving itself: a page with no drawings never reaches pdfplumber."""
    import pymupdf

    from helper.pdf_extractor import _has_table_rules

    data = build_pdf(tmp_path / "table.pdf")
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        admitted = [_has_table_rules(page) for page in doc]

    assert admitted == [False, True]


def test_unreadable_drawings_fail_open(app_modules):
    """An unreadable page is handed to pdfplumber, not silently dropped."""
    from helper.pdf_extractor import _has_table_rules

    class Hostile:
        rect = type("R", (), {"width": 612.0, "height": 792.0})()

        def get_cdrawings(self):
            raise RuntimeError("malformed content stream")

    assert _has_table_rules(Hostile()) is True


def test_pdf_ingests_end_to_end(app_modules, db, tmp_path):
    """The filter sits inside `ingest`; the document still completes."""
    data = build_pdf(tmp_path / "table.pdf")
    document, counts, duplicate = app_modules.documents.ingest(db, "table.pdf", data)

    assert document.status.value == "completed"
    assert duplicate is False
    assert counts["tables"] == 1
    assert counts["blocks"] > 0 and counts["chunks"] > 0


# --------------------------------------------------------------------------- #
# Batched embeddings
# --------------------------------------------------------------------------- #


@pytest.fixture()
def stub_embedder(app_modules, monkeypatch):
    """Replaces the network call with a deterministic, order-revealing one.

    Row i of the result is the unit vector for text i, so a scrambled or
    misaligned result is visible rather than merely plausible.
    """
    from llm import embedder

    dim = embedder.dimension()
    monkeypatch.setattr(embedder, "is_available", lambda: True)

    def encode(texts):
        rows = np.zeros((len(texts), dim), dtype=np.float32)
        for index, text in enumerate(texts):
            rows[index][int(text.split()[-1]) % dim] = 1.0
        return rows

    return embedder, encode


def _texts(count: int) -> list[str]:
    return [f"chunk {index}" for index in range(count)]


def test_batches_come_back_in_order(stub_embedder, monkeypatch):
    """Parallel batches must not reorder the result."""
    embedder, encode = stub_embedder
    monkeypatch.setattr(embedder, "_embed", encode)

    texts = _texts(200)  # seven batches of 32
    vectors = embedder.embed_documents(texts)

    assert len(vectors) == len(texts)
    assert all(int(np.argmax(vectors[i])) == i for i in range(len(texts)))


def test_one_failed_batch_keeps_the_others(stub_embedder, monkeypatch):
    """The regression: a single failure used to discard every other batch."""
    embedder, encode = stub_embedder
    calls = {"n": 0}

    def flaky(batch):
        calls["n"] += 1
        return None if calls["n"] == 2 else encode(batch)

    monkeypatch.setattr(embedder, "_embed", flaky)
    vectors = embedder.embed_documents(_texts(200))

    assert len(vectors) == 200
    assert sum(1 for vector in vectors if vector is None) == 32
    assert sum(1 for vector in vectors if vector is not None) == 168


def test_a_raising_batch_is_contained(stub_embedder, monkeypatch):
    """`_embed` should never raise, but a raise must not lose the good work."""
    embedder, encode = stub_embedder
    calls = {"n": 0}

    def exploding(batch):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("provider blew up")
        return encode(batch)

    monkeypatch.setattr(embedder, "_embed", exploding)
    vectors = embedder.embed_documents(_texts(200))

    assert len(vectors) == 200
    assert sum(1 for vector in vectors if vector is None) == 32


def test_short_response_is_dropped_not_misaligned(stub_embedder, monkeypatch):
    """A provider returning too few rows must not shift every later vector."""
    embedder, encode = stub_embedder
    monkeypatch.setattr(embedder, "_embed", lambda batch: encode(batch)[:5])

    vectors = embedder.embed_documents(_texts(64))

    assert len(vectors) == 64
    assert all(vector is None for vector in vectors)


def test_unavailable_returns_none_and_empty_is_empty(app_modules, monkeypatch):
    """None means 'nothing to retry'; [] means 'nothing was asked for'."""
    from llm import embedder

    monkeypatch.setattr(embedder, "is_available", lambda: False)
    assert embedder.embed_documents(_texts(10)) is None
    assert embedder.embed_documents([]) == []


def test_partial_embeddings_are_persisted(app_modules, db, tmp_path, monkeypatch):
    """A half embedded document still ingests, with the good vectors kept."""
    from llm import embedder

    dim = embedder.dimension()
    calls = {"n": 0}

    def half(texts):
        calls["n"] += 1
        if calls["n"] > 1:
            return None
        return np.eye(len(texts), dim, dtype=np.float32)

    monkeypatch.setattr(embedder, "is_available", lambda: True)
    monkeypatch.setattr(embedder, "_embed", half)

    from conftest import build_docx

    data = build_docx(tmp_path / "roadmap.docx")
    document, counts, _ = app_modules.documents.ingest(db, "roadmap.docx", data)

    assert document.status.value == "completed"

    from database.models import DocumentChunk

    stored = db.query(DocumentChunk).filter_by(document_id=document.id).all()
    assert len(stored) == counts["chunks"]
    assert any(chunk.embedding is not None for chunk in stored)
