from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import settings
from database.models import Document
from database.session import get_db
from helper.file_utils import UnsupportedFileType
from repository import document_repository as repository
from schema.chat_schema import AnswerResponse
from schema.document_schema import (
    DocumentDetail,
    DocumentListResponse,
    DocumentSummary,
    ExtractionCounts,
    UploadResponse,
)
from service import qa_service
from service.document_service import (
    DocumentTooLarge,
    EmptyUpload,
    ExtractionFailed,
    delete as delete_document,
    embed_document,
    ingest,
)

router = APIRouter()

_READ_CHUNK = 1024 * 1024


@router.post("/", response_model=UploadResponse)
async def _extract_document_details(
    file: UploadFile = File(..., description="A PDF or Word (.docx) document"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """Extract everything from an uploaded document and store it in SQLite.

    Text extraction and chunking happen synchronously so the response carries
    accurate counts. Embedding is deferred to a BackgroundTask so the caller
    does not wait for HuggingFace API round-trips.
    """
    data = await _read_upload(file)

    try:
        # `ingest` is fully synchronous - PDF parsing, chunking and summary
        # calls. Awaiting it on the event loop froze every other request for
        # the duration, so it runs on a worker thread instead.
        document, counts, already_processed = await run_in_threadpool(
            ingest, db, file.filename or "document", data
        )
    except EmptyUpload as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except UnsupportedFileType as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except DocumentTooLarge as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    except ExtractionFailed as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    # Schedule embedding AFTER the response is sent — the user gets their
    # response immediately; semantic search becomes available a few seconds
    # later once the background task finishes.
    if not already_processed:
        background_tasks.add_task(embed_document, document.id)

    return UploadResponse(
        document=DocumentDetail.model_validate(document),
        counts=ExtractionCounts(**counts),
        already_processed=already_processed,
    )


@router.get("/", response_model=AnswerResponse)
def _ask_questions(
    question: str = Query(..., min_length=1, max_length=2000),
    document_id: int | None = Query(None, description="Limit the answer to one document"),
    session_key: str | None = Query(None, description="Chat thread to continue"),
    top_k: int | None = Query(None, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Answer a question from the content extracted out of the documents."""
    if document_id is not None and repository.get(db, document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")

    return qa_service.ask(
        db,
        question=question,
        document_id=document_id,
        session_key=session_key,
        top_k=top_k,
    )


@router.post("/ask/stream")
@router.get("/stream")
def _ask_stream(
    question: str = Query(..., min_length=1, max_length=2000),
    document_id: int | None = Query(None, description="Limit the answer to one document"),
    session_key: str | None = Query(None, description="Chat thread to continue"),
    top_k: int | None = Query(None, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Stream an answer as Server-Sent Events for lower perceived latency."""
    if document_id is not None and repository.get(db, document_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")

    return StreamingResponse(
        qa_service.ask_stream(
            db,
            question=question,
            document_id=document_id,
            session_key=session_key,
            top_k=top_k,
        ),
        media_type="text/event-stream",
    )


@router.get("/documents", response_model=DocumentListResponse)
def _list_documents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List the uploaded documents, newest first."""
    items, total = repository.list_documents(db, limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentSummary.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def _get_document(document_id: int, db: Session = Depends(get_db)):
    return DocumentDetail.model_validate(_require(db, document_id))


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def _delete_document(document_id: int, db: Session = Depends(get_db)):
    delete_document(db, _require(db, document_id))


def _require(db: Session, document_id: int) -> Document:
    document = repository.get(db, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return document


async def _read_upload(file: UploadFile) -> bytes:
    """Read the upload, stopping as soon as it exceeds the configured limit."""
    parts: list[bytes] = []
    size = 0
    while chunk := await file.read(_READ_CHUNK):
        size += len(chunk)
        if size > settings.max_upload_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"The file is larger than the {settings.max_upload_mb} MB limit.",
            )
        parts.append(chunk)
    return b"".join(parts)
