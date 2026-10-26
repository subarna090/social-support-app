"""PDF to plain text with pypdf (research R1)."""

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class ExtractionError(Exception):
    """A document could not be read. The message is shown to applicants and caseworkers, so it
    never contains document content."""


def pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, ValueError, KeyError, OSError) as exc:
        raise ExtractionError("the PDF could not be opened") from exc
