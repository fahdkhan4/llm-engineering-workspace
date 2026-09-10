"""Single entry point for extraction: pick the parser that matches the file type."""

from __future__ import annotations

from database.models import FileType
from helper.docx_extractor import extract_docx
from helper.extraction_models import ExtractedDocument
from helper.pdf_extractor import extract_pdf

_EXTRACTORS = {
    FileType.PDF: extract_pdf,
    FileType.DOCX: extract_docx,
}


def extract_document(data: bytes, file_type: FileType) -> ExtractedDocument:
    extractor = _EXTRACTORS.get(file_type)
    if extractor is None:
        raise ValueError(f"No extractor registered for {file_type}.")
    return extractor(data)
