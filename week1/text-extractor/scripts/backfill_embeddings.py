"""Fill in chunk embeddings (and document summaries) for existing rows.

Documents ingested before embeddings existed - or while the embedding provider
was unreachable - have NULL vectors and are invisible to semantic search. This
repairs them.

    python -m scripts.backfill_embeddings
    python -m scripts.backfill_embeddings --force          # re-embed everything
    python -m scripts.backfill_embeddings --summaries      # summaries too

Deliberately not run at startup: it is a network job, and blocking the port
behind it - on every --reload edit - is the wrong trade.
"""

from __future__ import annotations

import argparse
import logging

from config import settings
from database.session import SessionLocal, init_db
from llm import embedder
from llm.llm_client import summarise_document
from repository import document_repository as repository

logger = logging.getLogger("backfill")

_MAX_ROWS = 100_000


def _backfill_embeddings(db, batch_size: int, force: bool) -> int:
    chunks = repository.chunks_missing_embeddings(db, _MAX_ROWS, include_all=force)
    if not chunks:
        print("Embeddings: nothing to do.")
        return 0

    print(f"Embeddings: {len(chunks)} chunk(s) to process with {settings.embedding_model}.")
    saved = 0
    for start in range(0, len(chunks), batch_size):
        window = chunks[start : start + batch_size]
        vectors = embedder.embed_documents([chunk.content for chunk in window])
        if vectors is None:
            print(f"  ! batch at offset {start} failed - stopping.")
            break
        saved += repository.store_embeddings(
            db, list(zip((chunk.id for chunk in window), vectors))
        )
        print(f"  {saved}/{len(chunks)}")
    return saved


def _backfill_summaries(db, force: bool) -> int:
    documents = repository.chunks_needing_summary(db, include_all=force)
    if not documents:
        print("Summaries: nothing to do.")
        return 0

    print(f"Summaries: {len(documents)} document(s) to process.")
    written = 0
    for document in documents:
        text = "\n\n".join(chunk.content for chunk in document.chunks)
        summary = summarise_document(
            text, title=document.title, page_count=document.page_count
        )
        if summary:
            repository.set_summary(db, document, summary)
            written += 1
            print(f"  {document.filename}: {summary[:70]}...")
        else:
            print(f"  ! {document.filename}: skipped")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Recompute rows that already have a value"
    )
    parser.add_argument("--batch", type=int, default=32, help="Texts per API call")
    parser.add_argument(
        "--summaries", action="store_true", help="Also backfill document summaries"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    init_db()

    if not embedder.is_available():
        print(
            "Embeddings are unavailable. Set HF_TOKEN in text-extractor/.env "
            "(and check embedding_enabled)."
        )
        return 1

    db = SessionLocal()
    try:
        _backfill_embeddings(db, args.batch, args.force)
        if args.summaries:
            _backfill_summaries(db, args.force)
        remaining = repository.missing_embedding_count(db)
    finally:
        db.close()

    print(f"Done. {remaining} chunk(s) still without an embedding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
