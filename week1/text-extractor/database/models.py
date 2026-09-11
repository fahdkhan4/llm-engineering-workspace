"""SQLAlchemy models describing how an extracted document is stored.

Storage layout
--------------
documents          one row per uploaded file (+ its metadata and status)
  document_blocks  the ordered structural content (headings, paragraphs, lists...)
  document_tables  tables kept both as markdown (for the LLM) and JSON (for the UI)
  document_chunks  retrieval units built from the blocks/tables, indexed by FTS5

chat_sessions      one chat thread from the frontend
  chat_messages    the turns of that thread, with the chunks used as sources
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"


class BlockType(str, enum.Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    HEADER = "header"
    FOOTER = "footer"
    CAPTION = "caption"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    filename: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str | None] = mapped_column(String(1024))
    file_type: Mapped[FileType] = mapped_column(Enum(FileType, native_enum=False))
    file_size: Mapped[int] = mapped_column(Integer)
    # sha256 of the raw bytes: re-uploading the same file returns the existing row.
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    title: Mapped[str | None] = mapped_column(String(512))
    author: Mapped[str | None] = mapped_column(String(512))
    subject: Mapped[str | None] = mapped_column(String(512))
    keywords: Mapped[str | None] = mapped_column(Text)
    # Written at ingest by the LLM. No single chunk is the document summary,
    # so questions about the document as a whole are answered from this.
    summary: Mapped[str | None] = mapped_column(Text)
    # Anything else the parser found (producer, created/modified dates, ...).
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    page_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    # Pages that produced (almost) no text - scanned images that would need OCR.
    ocr_required_pages: Mapped[list] = mapped_column(JSON, default=list)

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False),
        default=DocumentStatus.PENDING,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    blocks: Mapped[list[DocumentBlock]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    tables: Mapped[list[DocumentTable]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class DocumentBlock(Base):
    """One structural piece of the document, in reading order."""

    __tablename__ = "document_blocks"
    __table_args__ = (
        UniqueConstraint("document_id", "block_index", name="uq_block_order"),
        Index("ix_block_document_page", "document_id", "page_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )

    page_number: Mapped[int] = mapped_column(Integer, default=1)
    block_index: Mapped[int] = mapped_column(Integer)
    block_type: Mapped[BlockType] = mapped_column(Enum(BlockType, native_enum=False))
    heading_level: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # Layout hints: bounding box, font size, bold, list style, ...
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    document: Mapped[Document] = relationship(back_populates="blocks")


class DocumentTable(Base):
    """A table, stored twice: markdown for the LLM, JSON rows for the frontend."""

    __tablename__ = "document_tables"
    __table_args__ = (
        UniqueConstraint("document_id", "table_index", name="uq_table_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )

    page_number: Mapped[int] = mapped_column(Integer, default=1)
    table_index: Mapped[int] = mapped_column(Integer)
    n_rows: Mapped[int] = mapped_column(Integer, default=0)
    n_cols: Mapped[int] = mapped_column(Integer, default=0)
    content_markdown: Mapped[str] = mapped_column(Text)
    content_json: Mapped[list] = mapped_column(JSON, default=list)

    document: Mapped[Document] = relationship(back_populates="tables")


class DocumentChunk(Base):
    """Retrieval unit. document_chunks_fts keeps a full-text index of `content`."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )

    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # Nearest preceding heading - used as a citation label.
    section_title: Mapped[str | None] = mapped_column(String(512))
    page_start: Mapped[int] = mapped_column(Integer, default=1)
    page_end: Mapped[int] = mapped_column(Integer, default=1)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    # Reserved for the LLM layer: store a vector here if you add embeddings.
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)

    document: Mapped[Document] = relationship(back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(512))
    # Null means "ask across every document".
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, native_enum=False))
    content: Mapped[str] = mapped_column(Text)
    # Chunk ids / page numbers the answer was grounded on.
    sources: Mapped[list] = mapped_column(JSON, default=list)
    # Token count for this message turn (for session spend tracking)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="messages")
