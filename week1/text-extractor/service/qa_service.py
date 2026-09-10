"""Question -> retrieve from SQLite -> LLM -> answer. Behind GET /documents/ask."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from config import settings
from database.models import MessageRole
from llm.llm_client import (
    HistoryTurn,
    LLMNotConfigured,
    RetrievedContext,
    answer_question,
    rewrite_query,
)
from repository import chat_repository, document_repository
from schema.chat_schema import AnswerResponse, SourceRef

logger = logging.getLogger(__name__)

_EXCERPT_CHARS = 300
_OVERVIEW_LABEL = "document overview"
_NO_CONTEXT = (
    "I could not find anything about that in the uploaded documents. "
    "Try rephrasing the question, or upload the document that covers it."
)


@dataclass(slots=True)
class _Entry:
    """One numbered piece of evidence.

    Sources and contexts are both built from this single ordered list, so the
    [n] the model cites always refers to the same passage the reader clicks.
    """

    chunk_id: int
    document_id: int
    document_name: str
    section_title: str | None
    page_start: int
    page_end: int
    content: str
    score: float


def ask(
    db: Session,
    question: str,
    document_id: int | None = None,
    session_key: str | None = None,
    top_k: int | None = None,
) -> AnswerResponse:
    question = (question or "").strip()
    top_k = top_k or settings.retrieval_top_k

    session = chat_repository.get_or_create_session(db, session_key, document_id)
    # Read the history before recording this turn, so the question is not in it.
    history = [
        HistoryTurn(role=message.role.value, content=message.content)
        for message in chat_repository.recent_messages(db, session)
    ]
    chat_repository.add_message(db, session, MessageRole.USER, question)

    # Retrieval is keyword-based, so a follow-up like "more detail about it"
    # has to be resolved against the history before it can match anything.
    search_query = rewrite_query(question, history)
    if search_query != question:
        logger.info("Follow-up rewritten for retrieval: %r -> %r", question, search_query)

    document_ids = [document_id] if document_id else None
    hits = document_repository.search_chunks(
        db,
        search_query,
        limit=top_k,
        document_ids=document_ids,
        # The rewrite can strip the "about the whole document" signal, so the
        # retrieval layer needs the user's own wording too.
        original_question=question,
    )

    entries = _overview_entries(db, question, document_ids, hits) + [
        _Entry(
            chunk_id=hit.chunk.id,
            document_id=hit.chunk.document_id,
            document_name=hit.chunk.document.filename,
            section_title=hit.chunk.section_title,
            page_start=hit.chunk.page_start,
            page_end=hit.chunk.page_end,
            content=hit.chunk.content,
            score=hit.score,
        )
        for hit in hits
    ]

    logger.info(
        "Question %r (document_id=%s, top_k=%s): %d hit(s), %d source(s).",
        question,
        document_id,
        top_k,
        len(hits),
        len(entries),
    )

    sources = [
        SourceRef(
            index=position,
            chunk_id=entry.chunk_id,
            document_id=entry.document_id,
            document_name=entry.document_name,
            section_title=entry.section_title,
            page_start=entry.page_start,
            page_end=entry.page_end,
            score=round(entry.score, 4),
            excerpt=_excerpt(entry.content),
        )
        for position, entry in enumerate(entries, start=1)
    ]

    if not entries:
        return _respond(db, session, question, _NO_CONTEXT, sources, None, True)

    contexts = [
        RetrievedContext(
            chunk_id=entry.chunk_id,
            document_id=entry.document_id,
            document_name=entry.document_name,
            section_title=entry.section_title,
            page_start=entry.page_start,
            page_end=entry.page_end,
            content=entry.content,
            score=entry.score,
        )
        for entry in entries
    ]

    try:
        result = answer_question(question, contexts, history)
    except LLMNotConfigured as exc:
        # The retrieval half works; the frontend can be built against it already.
        logger.warning("LLM layer not implemented: %s", exc)
        return _respond(db, session, question, str(exc), sources, None, False)

    return _respond(db, session, question, result.answer, sources, result.model, True)


def _overview_entries(
    db: Session,
    question: str,
    document_ids: list[int] | None,
    hits: list,
) -> list[_Entry]:
    """Stored document summaries, for questions about a document as a whole.

    No chunk *is* the summary, so "what is this about?" cannot retrieve one.
    The overview is numbered and cited like any other source, carrying the
    document's first chunk id so the citation still resolves to a real passage.
    """
    if not document_repository.is_meta_question(question):
        return []

    # Sit level with the best passage rather than on a scale of their own; the
    # frontend normalises scores within one answer.
    score = hits[0].score if hits else 1.0
    return [
        _Entry(
            chunk_id=chunk.id,
            document_id=document.id,
            document_name=document.filename,
            section_title=_OVERVIEW_LABEL,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            content=document.summary,
            score=score,
        )
        for document, chunk in document_repository.documents_with_summary(
            db, document_ids
        )
    ]


def _respond(
    db: Session,
    session,
    question: str,
    answer: str,
    sources: list[SourceRef],
    model: str | None,
    llm_configured: bool,
) -> AnswerResponse:
    chat_repository.add_message(
        db,
        session,
        MessageRole.ASSISTANT,
        answer,
        sources=[source.model_dump(include={"chunk_id", "document_id", "page_start"}) for source in sources],
    )
    return AnswerResponse(
        question=question,
        answer=answer,
        session_key=session.session_key,
        sources=sources,
        model=model,
        llm_configured=llm_configured,
    )


def _excerpt(content: str) -> str:
    return content if len(content) <= _EXCERPT_CHARS else content[:_EXCERPT_CHARS] + "..."
