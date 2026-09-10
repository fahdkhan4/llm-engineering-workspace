"""Run one question against the live database and show why it matched.

    python -m scripts.verify_retrieval "What is this document about?"
    python -m scripts.verify_retrieval "load balancing" --document-id 1

Prints the extracted keyword terms, what each retrieval channel returned, and
the fused result - which turns "why are there no sources?" into one command.
"""

from __future__ import annotations

import argparse
import logging

from config import settings
from database import session as db_session
from database.session import SessionLocal, init_db
from llm import embedder
from repository import document_repository as repository


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--document-id", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=settings.retrieval_top_k)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    init_db()

    document_ids = [args.document_id] if args.document_id else None
    candidates = max(args.top_k, settings.retrieval_candidates)
    terms = repository._search_terms(args.question)

    db = SessionLocal()
    try:
        lexical = (
            repository._fts_search(db, terms, candidates, document_ids)
            if terms and db_session.fts_enabled
            else []
        )
        like = (
            repository._like_search(db, terms, candidates, document_ids)
            if terms
            else []
        )
        dense = repository._dense_search(db, args.question, candidates, document_ids)
        hits = repository.search_chunks(
            db,
            args.question,
            limit=args.top_k,
            document_ids=document_ids,
            original_question=args.question,
        )

        print(f"question        {args.question!r}")
        print(f"terms           {terms}")
        print(f"meta question   {repository.is_meta_question(args.question)}")
        print(f"fts_enabled     {db_session.fts_enabled}")
        print(f"embeddings      available={embedder.is_available()} "
              f"missing={repository.missing_embedding_count(db)}")
        print(f"fts hits        {len(lexical)}")
        print(f"like hits       {len(like)}")
        print(f"dense hits      {len(dense)}")
        print(f"fused           {len(hits)}")
        print()
        for position, hit in enumerate(hits, start=1):
            head = hit.chunk.content[:90].replace("\n", " ")
            print(
                f"  [{position}] score={hit.score:.4f} doc={hit.chunk.document_id} "
                f"chunk={hit.chunk.id} section={hit.chunk.section_title!r}"
            )
            print(f"       {head}...")
    finally:
        db.close()

    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
