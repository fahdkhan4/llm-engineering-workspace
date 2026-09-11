"""Chat threads and their message history."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import ChatMessage, ChatSession, MessageRole


def get_or_create_session(
    db: Session, session_key: str | None, document_id: int | None
) -> ChatSession:
    if session_key:
        existing = db.scalar(
            select(ChatSession).where(ChatSession.session_key == session_key)
        )
        if existing:
            return existing

    session = ChatSession(
        session_key=session_key or uuid.uuid4().hex,
        document_id=document_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def add_message(
    db: Session,
    session: ChatSession,
    role: MessageRole,
    content: str,
    sources: list | None = None,
    token_count: int = 0,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        sources=sources or [],
        token_count=token_count,
    )
    if session.title is None and role == MessageRole.USER:
        session.title = content[:120]

    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def recent_messages(db: Session, session: ChatSession, limit: int = 10) -> list[ChatMessage]:
    """Last `limit` turns, oldest first - ready to pass to the LLM as history."""
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


def session_turn_count(db: Session, session: ChatSession) -> int:
    """Return the total number of message turns recorded for this session."""
    from sqlalchemy import func

    count = db.scalar(
        select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session.id)
    )
    return count or 0


def session_total_tokens(db: Session, session: ChatSession) -> int:
    """Return the cumulative token consumption across all turns in this session."""
    from sqlalchemy import func

    total = db.scalar(
        select(func.coalesce(func.sum(ChatMessage.token_count), 0)).where(
            ChatMessage.session_id == session.id
        )
    )
    return total or 0
