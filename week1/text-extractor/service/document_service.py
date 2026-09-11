"""Upload -> extract -> store. The whole pipeline behind POST /documents."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from config import settings
from database.models import Document, DocumentStatus
from database.session import get_db
from helper.chunker import build_chunks
from helper.document_extraction import extract_document
from helper.file_utils import UnsupportedFileType, detect_file_type, sha256_hex, stored_filename
from llm.llm_client import summarise_document
from repository import document_repository as repository
from repository.document_repository import backfill_document_embeddings

logger = logging.getLogger(__name__)


class DocumentTooLarge(ValueError):
    pass


class EmptyUpload(ValueError):
    pass


class ExtractionFailed(RuntimeError):
    pass


def ingest(db: Session, filename: str, data: bytes) -> tuple[Document, dict, bool]:
    """Store and fully extract one uploaded file.

    Returns the document, its content counts, and whether it was already
    processed (the same bytes uploaded twice are not parsed again).
    """
    if not data:
        raise EmptyUpload("The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise DocumentTooLarge(
            f"The file is larger than the {settings.max_upload_mb} MB limit."
        )

    file_type = detect_file_type(filename, data)  # raises UnsupportedFileType
    content_hash = sha256_hex(data)

    existing = repository.get_by_hash(db, content_hash)
    if existing is not None and existing.status == DocumentStatus.COMPLETED:
        return existing, repository.counts(db, existing.id), True

    stored_path = _store_file(data, content_hash, file_type)

    if existing is not None:
        # A previous attempt failed or was interrupted: start its content over.
        repository.clear_content(db, existing.id)
        existing.status = DocumentStatus.PROCESSING
        existing.stored_path = stored_path
        db.commit()
        document = existing
    else:
        document = repository.create(
            db,
            filename=Path(filename or "document").name,
            file_type=file_type,
            file_size=len(data),
            content_hash=content_hash,
            stored_path=stored_path,
        )

    try:
        extracted = extract_document(data, file_type)
        chunks = build_chunks(
            extracted.blocks, settings.chunk_size, settings.chunk_overlap
        )
        repository.save_extraction(db, document, extracted, chunks)
    except Exception as exc:
        logger.exception("Extraction failed for %s", document.filename)
        # The commit may be what failed, which leaves the session unusable.
        db.rollback()
        repository.mark_failed(db, document, str(exc))
        raise ExtractionFailed(f"Could not extract the document: {exc}") from exc

    _summarise(db, document, extracted)
    return document, repository.counts(db, document.id), False


def embed_document(document_id: int) -> None:
    """Embed all unembedded chunks for *document_id*.

    Designed to run as a FastAPI BackgroundTask after the upload response
    has already been sent. Opens its own DB session so the request session
    is not shared across threads.
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        backfill_document_embeddings(db, document_id)
    except Exception:
        logger.warning(
            "Background embedding failed for document %d.", document_id, exc_info=True
        )
    finally:
        try:
            next(db_gen)  # triggers the generator's finally / session.close()
        except StopIteration:
            pass


def _summarise(db: Session, document: Document, extracted) -> None:
    """Store a document-level overview. Best effort - never fails the upload."""
    try:
        summary = summarise_document(
            extracted.text, title=document.title, page_count=document.page_count
        )
        if summary:
            repository.set_summary(db, document, summary)
    except Exception:
        logger.warning("Could not summarise %s", document.filename, exc_info=True)


def delete(db: Session, document: Document) -> None:
    """Remove the document, its extracted content and the stored upload."""
    path = document.stored_path
    repository.delete_document(db, document)
    if path:
        Path(path).unlink(missing_ok=True)


def _store_file(data: bytes, content_hash: str, file_type) -> str | None:
    if not settings.keep_uploaded_files:
        return None
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / stored_filename(content_hash, file_type)
    if not path.exists():
        path.write_bytes(data)
    return str(path)
