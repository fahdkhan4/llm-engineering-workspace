"""Retrieval regression tests.

The bug these lock down: every question phrased *about* a document - "what is
this document about?" - returned zero sources, because retrieval was keyword
only and those words appear nowhere in the prose.
"""

from __future__ import annotations

import os

import pytest

from conftest import build_docx


@pytest.fixture()
def ingested(app_modules, db, tmp_path):
    data = build_docx(tmp_path / "roadmap.docx")
    document, counts, _ = app_modules.documents.ingest(db, "roadmap.docx", data)
    assert counts["chunks"] > 0, "the fixture document produced no chunks"
    return document


# --------------------------------------------------------------------------- #
# The regression
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "question",
    [
        "What is this document about?",
        "Summarize this document",
        "Give me a summary",
        "what the document is about",
    ],
)
def test_meta_questions_return_sources(app_modules, db, ingested, question):
    """None of these words appear in the document. They must still resolve."""
    answer = app_modules.qa.ask(db, question=question)

    assert answer.sources, f"{question!r} returned no sources"
    assert all(source.document_id == ingested.id for source in answer.sources)
    assert "could not find anything" not in answer.answer.lower()


def test_keyword_question_still_matches_its_chunk(app_modules, db, ingested):
    """Guard against the semantic half drowning out exact-term search."""
    hits = app_modules.repository.search_chunks(db, "sharding partition key", limit=6)

    assert hits
    assert "Sharding" in hits[0].chunk.content


def test_empty_corpus_still_reports_nothing_found(app_modules, db):
    """The 'not found' path is still reachable when there is genuinely no data."""
    answer = app_modules.qa.ask(db, question="What is this document about?")

    assert answer.sources == []
    assert "could not find anything" in answer.answer.lower()


def test_sources_are_index_aligned(app_modules, db, ingested):
    """The [n] the model cites must be the source the reader clicks."""
    answer = app_modules.qa.ask(db, question="What is this document about?")

    assert [source.index for source in answer.sources] == list(
        range(1, len(answer.sources) + 1)
    )


def test_document_filter_scopes_results(app_modules, db, ingested):
    answer = app_modules.qa.ask(db, question="sharding", document_id=ingested.id)

    assert answer.sources
    assert {source.document_id for source in answer.sources} == {ingested.id}


# --------------------------------------------------------------------------- #
# Fusion, in isolation
# --------------------------------------------------------------------------- #


def test_rrf_prefers_a_chunk_both_channels_found(app_modules):
    fuse = app_modules.repository._rrf_fuse

    # 2 is second in each list; 1 and 3 lead one list apiece.
    fused = fuse([[(1, 9.0), (2, 5.0)], [(3, 0.9), (2, 0.8)]], k=60, limit=3)

    assert fused[0][0] == 2


def test_rrf_keeps_a_single_channel_result(app_modules):
    """The failing case: BM25 matches nothing and dense carries the answer."""
    fuse = app_modules.repository._rrf_fuse

    fused = fuse([[], [(7, 0.8), (8, 0.7)]], k=60, limit=5)

    assert [chunk_id for chunk_id, _ in fused] == [7, 8]


def test_rrf_of_nothing_is_nothing(app_modules):
    assert app_modules.repository._rrf_fuse([], k=60, limit=5) == []


# --------------------------------------------------------------------------- #
# Vector round-trip
# --------------------------------------------------------------------------- #


def test_vector_roundtrip(app_modules):
    import numpy as np

    repository = app_modules.repository
    vector = np.arange(app_modules.settings.embedding_dim, dtype=np.float32)

    decoded = repository._decode_vector(repository._encode_vector(vector))

    assert decoded is not None
    np.testing.assert_array_equal(decoded, vector)


def test_wrong_dimension_vectors_are_skipped_not_fatal(app_modules):
    """A model swap must degrade, not crash every question."""
    assert app_modules.repository._decode_vector(b"\x00" * 16) is None
    assert app_modules.repository._decode_vector(None) is None


# --------------------------------------------------------------------------- #
# Dense channel - only when a token is configured
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(not os.getenv("HF_TOKEN"), reason="HF_TOKEN is not set")
def test_semantic_paraphrase_matches_without_shared_words(tmp_path, monkeypatch):
    """The real payoff: a question sharing no keyword with the text."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'dense.db'}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("GROQ_API_KEY", "")

    from conftest import _reset_app_modules

    _reset_app_modules()
    import config

    config.get_settings.cache_clear()

    from database.session import SessionLocal, init_db
    from repository import document_repository
    from service import document_service

    init_db()
    db = SessionLocal()
    try:
        data = build_docx(tmp_path / "roadmap.docx")
        document_service.ingest(db, "roadmap.docx", data)
        assert document_repository.missing_embedding_count(db) == 0

        # "splitting records across servers" shares no term with the chunk,
        # which says "Sharding splits a table across machines".
        hits = document_repository._dense_search(
            db, "splitting records across many servers", 10, None
        )
        assert hits, "the semantic channel returned nothing"
    finally:
        db.close()
        _reset_app_modules()
