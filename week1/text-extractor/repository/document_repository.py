"""All database access for documents, their content and retrieval."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import numpy as np
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from config import settings
from database import session as db_session
from database.models import (
    Document,
    DocumentBlock,
    DocumentChunk,
    DocumentStatus,
    DocumentTable,
    FileType,
)
from helper.chunker import Chunk
from helper.extraction_models import ExtractedDocument
from llm import embedder

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
# Words too common to help ranking; dropping them keeps the OR query focused.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do", "does",
    "for", "from", "has", "have", "how", "in", "is", "it", "its", "me", "of", "on",
    "or", "tell", "that", "the", "this", "to", "was", "were", "what", "when",
    "where", "which", "who", "why", "will", "with", "you", "your",
}

# Questions about the document as a whole. No single chunk *is* the summary,
# so these also pull in the opening chunks - see `leading_chunks`.
_META_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # "what is this document about", "what the document is about",
        # "what's it about", "what are these files about"
        r"\bwhat(?:'?s| is| are)?\s+(?:this|these|those|the|it)\s+"
        r"(?:document|file|pdf|paper|report)?s?\s*(?:is\s+|are\s+)?about\b",
        r"\bwhat(?:'?s| is)\s+(?:it|this|that)\s+about\b",
        r"\btell me about (?:this|the|these)\s+(?:document|file|pdf|paper|report)s?\b",
        r"\bsummar(y|ise|ize|ies)\b",
        r"\boverview\b",
        r"\btl;?dr\b",
        r"\bmain (point|idea|topic|theme|takeaway)s?\b",
        r"\bkey (point|takeaway|finding|idea)s?\b",
        r"\bwhat does\s+(?:this|it|that|the)\s+"
        r"(?:document|file|pdf|paper|report)?s?\s*(?:say|cover|contain|discuss)\b",
        r"\bwhat (topics|subjects) .* (cover|discuss|contain)\b",
        r"\bthe gist\b",
    )
]


# Cosine below this is noise rather than a weak match. Normalised BGE vectors
# put genuinely unrelated text around 0.1-0.3 and real matches above 0.5.
_DENSE_SCORE_FLOOR = 0.25


@dataclass(slots=True)
class ChunkHit:
    chunk: DocumentChunk
    score: float


def is_meta_question(question: str) -> bool:
    return any(pattern.search(question or "") for pattern in _META_PATTERNS)


def _encode_vector(vector) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _decode_vector(blob: bytes | None) -> np.ndarray | None:
    """Bytes back to a vector, skipping rows written by a different model.

    Returning None instead of raising means a model swap degrades to
    "those chunks are not semantically searchable until the backfill reruns"
    rather than breaking every question.
    """
    if not blob:
        return None
    expected = settings.embedding_dim
    if len(blob) != expected * 4:
        logger.debug(
            "Skipping embedding of %d bytes (expected %d for dim %d).",
            len(blob),
            expected * 4,
            expected,
        )
        return None
    return np.frombuffer(blob, dtype=np.float32)


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #


def get(db: Session, document_id: int) -> Document | None:
    return db.get(Document, document_id)


def get_by_hash(db: Session, content_hash: str) -> Document | None:
    return db.scalar(select(Document).where(Document.content_hash == content_hash))


def list_documents(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    status: DocumentStatus | None = None,
) -> tuple[list[Document], int]:
    query = select(Document)
    count_query = select(func.count()).select_from(Document)
    if status is not None:
        query = query.where(Document.status == status)
        count_query = count_query.where(Document.status == status)

    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total


def create(
    db: Session,
    *,
    filename: str,
    file_type: FileType,
    file_size: int,
    content_hash: str,
    stored_path: str | None,
) -> Document:
    document = Document(
        filename=filename,
        file_type=file_type,
        file_size=file_size,
        content_hash=content_hash,
        stored_path=stored_path,
        status=DocumentStatus.PROCESSING,
        extra_metadata={},
        ocr_required_pages=[],
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def save_extraction(
    db: Session, document: Document, extracted: ExtractedDocument, chunks: list[Chunk]
) -> Document:
    """Persist blocks, tables and chunks, then mark the document completed."""
    metadata = dict(extracted.metadata)

    document.title = _trim(metadata.pop("title", None), 512) or document.filename
    document.author = _trim(metadata.pop("author", None), 512)
    document.subject = _trim(metadata.pop("subject", None), 512)
    document.keywords = metadata.pop("keywords", None)
    document.extra_metadata = metadata
    document.page_count = extracted.page_count
    document.word_count = extracted.word_count
    document.char_count = extracted.char_count
    document.ocr_required_pages = extracted.ocr_required_pages
    document.status = DocumentStatus.COMPLETED
    document.error_message = None

    db.add_all(
        DocumentBlock(
            document_id=document.id,
            page_number=block.page_number,
            block_index=index,
            block_type=block.block_type,
            heading_level=block.heading_level,
            content=block.content,
            meta=block.meta,
        )
        for index, block in enumerate(extracted.blocks)
    )
    db.add_all(
        DocumentTable(
            document_id=document.id,
            page_number=table.page_number,
            table_index=table.table_index,
            n_rows=table.n_rows,
            n_cols=table.n_cols,
            content_markdown=table.markdown,
            content_json=table.rows,
        )
        for table in extracted.tables
    )
    # Batched, and tolerant per batch: whatever fails comes back as None, so a
    # bad request costs those chunks only. The document still ingests and stays
    # keyword-searchable; scripts.backfill_embeddings repairs the gaps.
    vectors = embedder.embed_documents([chunk.content for chunk in chunks])
    if vectors is None:
        vectors = [None] * len(chunks)

    missing = sum(1 for vector in vectors if vector is None)
    if missing:
        logger.warning(
            "%d of %d chunk(s) of %s have no embedding - semantic search will skip "
            "them until 'python -m scripts.backfill_embeddings' is run.",
            missing,
            len(chunks),
            document.filename,
        )

    db.add_all(
        DocumentChunk(
            document_id=document.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            section_title=_trim(chunk.section_title, 512),
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            char_count=chunk.char_count,
            token_estimate=chunk.token_estimate,
            embedding=(
                _encode_vector(vectors[index]) if vectors[index] is not None else None
            ),
        )
        for index, chunk in enumerate(chunks)
    )

    db.commit()
    db.refresh(document)
    return document


def mark_failed(db: Session, document: Document, message: str) -> Document:
    document.status = DocumentStatus.FAILED
    document.error_message = message[:2000]
    db.commit()
    db.refresh(document)
    return document


def clear_content(db: Session, document_id: int) -> None:
    """Remove previously extracted content so a document can be re-processed."""
    for model in (DocumentBlock, DocumentTable, DocumentChunk):
        db.execute(delete(model).where(model.document_id == document_id))
    db.commit()


def delete_document(db: Session, document: Document) -> None:
    # Delete chunks explicitly so the FTS triggers always fire.
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    db.delete(document)
    db.commit()


def counts(db: Session, document_id: int) -> dict[str, int]:
    return {
        "blocks": _count(db, DocumentBlock, document_id),
        "tables": _count(db, DocumentTable, document_id),
        "chunks": _count(db, DocumentChunk, document_id),
    }


def _count(db: Session, model, document_id: int) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(model).where(model.document_id == document_id)
        )
        or 0
    )


def documents_with_summary(
    db: Session, document_ids: list[int] | None = None, limit: int = 3
) -> list[tuple[Document, DocumentChunk]]:
    """Completed documents that have a stored summary, with their first chunk.

    The first chunk comes along so the overview can be cited like any other
    source: the citation number resolves to a real passage in the document.
    """
    query = select(Document).where(
        Document.status == DocumentStatus.COMPLETED,
        Document.summary.is_not(None),
    )
    if document_ids:
        query = query.where(Document.id.in_(document_ids))

    pairs: list[tuple[Document, DocumentChunk]] = []
    for document in db.scalars(query.order_by(Document.id).limit(limit)).all():
        first = db.scalar(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
            .limit(1)
        )
        if first is not None:
            pairs.append((document, first))
    return pairs


def chunks_needing_summary(db: Session, include_all: bool = False) -> list[Document]:
    """Completed documents with no summary yet - the summary backfill queue."""
    query = select(Document).where(Document.status == DocumentStatus.COMPLETED)
    if not include_all:
        query = query.where(Document.summary.is_(None))
    return list(db.scalars(query.order_by(Document.id)).all())


def set_summary(db: Session, document: Document, summary: str | None) -> None:
    document.summary = summary
    db.commit()


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #


def missing_embedding_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.embedding.is_(None))
        )
        or 0
    )


def chunks_missing_embeddings(
    db: Session, limit: int, include_all: bool = False
) -> list[DocumentChunk]:
    """Chunks with no vector yet - the work queue for the backfill script."""
    query = select(DocumentChunk)
    if not include_all:
        query = query.where(DocumentChunk.embedding.is_(None))
    return list(db.scalars(query.order_by(DocumentChunk.id).limit(limit)).all())


def store_embeddings(db: Session, pairs: list[tuple[int, object]]) -> int:
    """Write vectors back for the given chunk ids. Returns how many were saved.

    Pairs whose vector is None are skipped: a batch the provider could not
    embed leaves the existing value alone rather than nulling it.
    """
    written = 0
    for chunk_id, vector in pairs:
        if vector is None:
            continue
        db.execute(
            DocumentChunk.__table__.update()
            .where(DocumentChunk.id == chunk_id)
            .values(embedding=_encode_vector(vector))
        )
        written += 1

    if written:
        db.commit()
    return written


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #


def search_chunks(
    db: Session,
    question: str,
    limit: int,
    document_ids: list[int] | None = None,
    original_question: str | None = None,
) -> list[ChunkHit]:
    """Rank chunks against the question, fusing keyword and semantic search.

    Keyword search (FTS5/BM25, or LIKE where FTS5 is missing) is precise for
    exact terms, names and numbers. Semantic search covers questions whose
    wording never appears in the text. Their scores are not comparable, so the
    two rankings are merged by Reciprocal Rank Fusion, which needs only ranks.

    `original_question` is the user's untouched wording. It matters because the
    caller passes an LLM-rewritten query here, and the rewrite can turn
    "what is this about?" into topic keywords, destroying the signal that this
    is a question about the document as a whole.
    """
    original_question = original_question or question
    candidates = max(limit, settings.retrieval_candidates)

    # May legitimately be empty - the semantic channel still has something to do.
    terms = _search_terms(question)

    lexical: list[tuple[int, float]] = []
    branch = "none"
    if terms:
        if db_session.fts_enabled:
            lexical = _fts_search(db, terms, candidates, document_ids)
            branch = "fts"
        if not lexical:
            lexical = _like_search(db, terms, candidates, document_ids)
            branch = "like"

    dense = _dense_search(db, question, candidates, document_ids)

    channels = [channel for channel in (lexical, dense) if channel]

    # No single chunk *is* the document summary, so a "what is this about?"
    # question gets the opening chunks as an extra channel. The same channel
    # rescues any question the other two could not match at all.
    leading: list[tuple[int, float]] = []
    if is_meta_question(original_question) or not channels:
        leading = _leading_ranked(db, document_ids, candidates)
        if leading:
            channels.append(leading)

    ranked = _rrf_fuse(channels, settings.rrf_k, limit)
    hits = _load_hits(db, ranked)

    log = logger.info if not hits else logger.debug
    log(
        "Retrieval: terms=%s fts_enabled=%s lexical=%d(%s) dense=%d leading=%d "
        "-> fused=%d (limit=%d, docs=%s)",
        terms,
        db_session.fts_enabled,
        len(lexical),
        branch,
        len(dense),
        len(leading),
        len(hits),
        limit,
        document_ids or "all",
    )
    return hits


def _fts_search(
    db: Session, terms: list[str], candidates: int, document_ids: list[int] | None
) -> list[tuple[int, float]]:
    match = " OR ".join(f'"{term}"' for term in terms)
    filter_sql = ""
    params: dict = {"match": match, "limit": candidates}
    if document_ids:
        placeholders = ", ".join(f":doc{i}" for i in range(len(document_ids)))
        filter_sql = f"AND c.document_id IN ({placeholders})"
        params.update({f"doc{i}": doc_id for i, doc_id in enumerate(document_ids)})

    fts = db_session.FTS_TABLE
    sql = text(
        f"""
        SELECT c.id AS chunk_id,
               bm25({fts}, 1.0, 2.0) AS score
        FROM {fts}
        JOIN document_chunks c ON c.id = {fts}.rowid
        WHERE {fts} MATCH :match {filter_sql}
        ORDER BY score
        LIMIT :limit
        """
    )

    try:
        rows = db.execute(sql, params).all()
    except Exception:
        # Logged, not swallowed: a broken FTS index and an honest zero-match
        # produce the same empty list, and only the log tells them apart.
        logger.exception("FTS5 query failed (match=%r) - falling back to LIKE.", match)
        return []
    # bm25() is negative and lower is better; flip it so bigger means more relevant.
    return [(row.chunk_id, -float(row.score)) for row in rows]


def _like_search(
    db: Session, terms: list[str], candidates: int, document_ids: list[int] | None
) -> list[tuple[int, float]]:
    conditions = [
        func.lower(DocumentChunk.content).like(f"%{term.lower()}%") for term in terms
    ]
    query = select(DocumentChunk.id, DocumentChunk.content)
    if document_ids:
        query = query.where(DocumentChunk.document_id.in_(document_ids))

    # Over-fetch, then rank in Python by how often the terms actually occur.
    rows = db.execute(query.where(or_(*conditions)).limit(candidates * 5)).all()

    scored = [
        (chunk_id, _overlap_score(content, terms)) for chunk_id, content in rows
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:candidates]


def _dense_search(
    db: Session, question: str, candidates: int, document_ids: list[int] | None
) -> list[tuple[int, float]]:
    """Cosine similarity between the question and every stored chunk vector.

    Brute force on purpose. At 1024 dims a chunk vector is 4 KB, and an
    (N, 1024) @ (1024,) float32 product stays sub-millisecond well past 10k
    chunks - decoding the blobs costs more than the arithmetic. Revisit with a
    real vector index (sqlite-vec, faiss) somewhere north of ~20k chunks.
    """
    query_vector = embedder.embed_query(question)
    if query_vector is None:
        return []

    query = select(DocumentChunk.id, DocumentChunk.embedding).where(
        DocumentChunk.embedding.is_not(None)
    )
    if document_ids:
        query = query.where(DocumentChunk.document_id.in_(document_ids))

    ids: list[int] = []
    vectors: list[np.ndarray] = []
    for chunk_id, blob in db.execute(query).all():
        vector = _decode_vector(blob)
        if vector is not None:
            ids.append(chunk_id)
            vectors.append(vector)

    if not ids:
        logger.debug("No usable chunk embeddings - semantic channel is empty.")
        return []

    # Both sides are unit length, so the dot product is the cosine similarity.
    scores = np.vstack(vectors) @ query_vector
    order = np.argsort(-scores)[:candidates]
    return [
        (ids[i], float(scores[i])) for i in order if scores[i] >= _DENSE_SCORE_FLOOR
    ]


def _leading_ranked(
    db: Session, document_ids: list[int] | None, candidates: int
) -> list[tuple[int, float]]:
    """The opening chunks of each in-scope document, in reading order.

    These are real, citable chunks - they carry a valid chunk id, page and
    section - so they flow through `SourceRef` and the frontend unchanged.
    In practice a document's first chunks are its title, intro and structure,
    which is exactly what "what is this about?" is asking for.
    """
    query = (
        select(DocumentChunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.status == DocumentStatus.COMPLETED,
            DocumentChunk.chunk_index < settings.fallback_leading_chunks,
        )
    )
    if document_ids:
        query = query.where(DocumentChunk.document_id.in_(document_ids))

    query = query.order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    rows = db.scalars(query.limit(candidates)).all()
    # RRF reads rank, not score, so the value here is only a placeholder.
    return [(chunk_id, 0.0) for chunk_id in rows]


def _rrf_fuse(
    ranked_lists: list[list[tuple[int, float]]], k: int, limit: int
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: score(d) = sum over channels of 1 / (k + rank).

    Rank-based on purpose. BM25 is unbounded and corpus-dependent while cosine
    sits in a narrow positive band, so the two cannot be put on one scale; and
    min-max normalising is degenerate here, where a channel routinely returns
    one or two candidates and would collapse to exactly {0.0, 1.0}. RRF also
    handles a chunk found by only one channel correctly, which is the whole
    point when BM25 matches nothing.
    """
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, (chunk_id, _score) in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ordered[:limit]


def _overlap_score(content: str, terms: list[str]) -> float:
    lowered = content.lower()
    return sum(lowered.count(term.lower()) for term in terms) / (len(content) ** 0.5 or 1)


def _load_hits(db: Session, ranked: list[tuple[int, float]]) -> list[ChunkHit]:
    if not ranked:
        return []
    ids = [chunk_id for chunk_id, _ in ranked]
    chunks = db.scalars(
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .where(DocumentChunk.id.in_(ids))
    ).all()
    by_id = {chunk.id: chunk for chunk in chunks}
    return [
        ChunkHit(chunk=by_id[chunk_id], score=score)
        for chunk_id, score in ranked
        if chunk_id in by_id
    ]


def _search_terms(question: str) -> list[str]:
    """Reduce free text to safe FTS terms (user input must never reach the parser)."""
    words = [word.lower() for word in _WORD_RE.findall(question or "")]
    terms = [word for word in words if len(word) > 2 and word not in _STOPWORDS]
    if not terms:
        terms = [word for word in words if len(word) > 1]
    # Keep the order but drop duplicates.
    return list(dict.fromkeys(terms))[:32]


def _trim(value, length: int) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value[:length] if value else None
