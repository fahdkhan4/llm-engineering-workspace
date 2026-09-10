"""Upload helpers: hashing, type sniffing and safe storage names."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

from database.models import FileType

_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"
_EXTENSIONS = {".pdf": FileType.PDF, ".docx": FileType.DOCX}


class UnsupportedFileType(ValueError):
    """Raised for anything that is not a PDF or a .docx file."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_file_type(filename: str, data: bytes) -> FileType:
    """Trust the bytes, not the extension: the filename comes from the client."""
    if data.startswith(_PDF_MAGIC):
        return FileType.PDF

    if data.startswith(_ZIP_MAGIC):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "word/document.xml" in archive.namelist():
                    return FileType.DOCX
        except zipfile.BadZipFile:
            pass
        raise UnsupportedFileType(
            "Only Word .docx files are supported (this looks like another Office format)."
        )

    suffix = Path(filename or "").suffix.lower()
    if suffix == ".doc":
        raise UnsupportedFileType(
            "Legacy .doc files are not supported. Please save the file as .docx."
        )
    if suffix in _EXTENSIONS:
        # Extension says PDF/DOCX but the content does not match.
        raise UnsupportedFileType(f"The file is not a valid {suffix[1:].upper()} document.")

    raise UnsupportedFileType("Unsupported file type. Upload a PDF or a Word .docx file.")


def stored_filename(content_hash: str, file_type: FileType) -> str:
    """Content-addressed name, so a client-supplied path can never escape the folder."""
    return f"{content_hash}.{file_type.value}"
