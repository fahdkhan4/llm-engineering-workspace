"""SQLite engine, session factory and schema bootstrap."""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from database.models import Base

logger = logging.getLogger(__name__)

FTS_TABLE = "document_chunks_fts"

engine = create_engine(
    settings.database_url,
    # FastAPI serves requests from a threadpool, so the connection must be shareable.
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    """SQLite needs these per connection; they are off by default."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")  # honour ON DELETE CASCADE
    cursor.execute("PRAGMA recursive_triggers=ON")  # keep FTS in sync on cascades
    cursor.execute("PRAGMA journal_mode=WAL")  # readers do not block the writer
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


# FTS5 mirror of document_chunks: keyword retrieval without an embedding model.
# `content=` makes it an external-content index, so text is not stored twice.
_FTS_STATEMENTS = [
    f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
        content,
        section_title,
        content='document_chunks',
        content_rowid='id',
        tokenize='porter unicode61'
    )
    """,
    f"""
    CREATE TRIGGER IF NOT EXISTS document_chunks_fts_ai
    AFTER INSERT ON document_chunks BEGIN
        INSERT INTO {FTS_TABLE}(rowid, content, section_title)
        VALUES (new.id, new.content, new.section_title);
    END
    """,
    f"""
    CREATE TRIGGER IF NOT EXISTS document_chunks_fts_ad
    AFTER DELETE ON document_chunks BEGIN
        INSERT INTO {FTS_TABLE}({FTS_TABLE}, rowid, content, section_title)
        VALUES ('delete', old.id, old.content, old.section_title);
    END
    """,
    f"""
    CREATE TRIGGER IF NOT EXISTS document_chunks_fts_au
    AFTER UPDATE ON document_chunks BEGIN
        INSERT INTO {FTS_TABLE}({FTS_TABLE}, rowid, content, section_title)
        VALUES ('delete', old.id, old.content, old.section_title);
        INSERT INTO {FTS_TABLE}(rowid, content, section_title)
        VALUES (new.id, new.content, new.section_title);
    END
    """,
]

# Nullable columns added after the first release: (table, column, type).
_ADDED_COLUMNS = [
    ("documents", "summary", "TEXT"),
    ("chat_messages", "token_count", "INTEGER DEFAULT 0"),
]

# Set by init_db(); the retrieval layer falls back to LIKE when FTS5 is missing.
fts_enabled = False


def _database_path() -> Path | None:
    url = settings.database_url
    prefix = "sqlite:///"
    return Path(url[len(prefix) :]) if url.startswith(prefix) else None


def init_db(db_engine: Engine | None = None) -> None:
    """Create tables, the FTS index and the folders the app writes to."""
    global fts_enabled
    db_engine = db_engine or engine

    db_path = _database_path()
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(db_engine)
    _add_missing_columns(db_engine)

    try:
        with db_engine.begin() as conn:
            for statement in _FTS_STATEMENTS:
                conn.execute(text(statement))
        fts_enabled = True
    except Exception:  # SQLite build without the FTS5 module
        fts_enabled = False
        logger.warning("FTS5 unavailable - falling back to LIKE search for retrieval.")

    _warn_about_missing_embeddings(db_engine)


def _add_missing_columns(db_engine: Engine) -> None:
    """`create_all` only creates missing tables, never missing columns.

    There is no migration tool here, so nullable columns added after a database
    already exists are applied by hand. If this list grows past a couple of
    entries, adopt Alembic instead of extending it.
    """
    for table, column, ddl in _ADDED_COLUMNS:
        with db_engine.begin() as conn:
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))
            }
            if not existing or column in existing:
                continue
            logger.info("Adding missing column %s.%s", table, column)
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def _warn_about_missing_embeddings(db_engine: Engine) -> None:
    """Point at the backfill instead of silently degrading to keyword-only."""
    try:
        with db_engine.connect() as conn:
            missing = conn.execute(
                text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NULL")
            ).scalar()
    except Exception:  # brand-new database, or a table that is not there yet
        return

    if missing:
        logger.warning(
            "%d chunk(s) have no embedding - semantic search will skip them. "
            "Run: python -m scripts.backfill_embeddings",
            missing,
        )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
