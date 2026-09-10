"""Request/response models for the document endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from database.models import DocumentStatus, FileType


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: FileType
    file_size: int
    title: str | None = None
    author: str | None = None
    page_count: int
    word_count: int
    status: DocumentStatus
    created_at: datetime


class DocumentDetail(DocumentSummary):
    subject: str | None = None
    keywords: str | None = None
    char_count: int
    extra_metadata: dict = Field(default_factory=dict)
    # Pages with no extractable text: scans that would need OCR to be searchable.
    ocr_required_pages: list[int] = Field(default_factory=list)
    error_message: str | None = None


class ExtractionCounts(BaseModel):
    blocks: int
    tables: int
    chunks: int


class UploadResponse(BaseModel):
    document: DocumentDetail
    counts: ExtractionCounts
    # True when the same file had already been uploaded, so nothing was re-parsed.
    already_processed: bool = False


class DocumentListResponse(BaseModel):
    items: list[DocumentSummary]
    total: int
    limit: int
    offset: int
