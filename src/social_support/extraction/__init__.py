"""Non-LLM document extraction (feature 004): pypdf text, local OCR and spreadsheet reading.

An outer adapter layer: imports ``domain`` only, never ``persistence``, ``services``, ``api``,
``ui`` or ``synthetic``.
"""

import time
from datetime import date

from social_support.domain.documents import DocumentType, ExtractedDocument
from social_support.extraction import (
    assets_liabilities,
    bank_statement,
    credit_report,
    emirates_id,
    resume,
)
from social_support.extraction.common import failed
from social_support.extraction.pdf_text import ExtractionError

MAX_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"
EXPECTED_KIND = {
    DocumentType.BANK_STATEMENT: ("PDF", (PDF_MAGIC,)),
    DocumentType.RESUME: ("PDF", (PDF_MAGIC,)),
    DocumentType.CREDIT_REPORT: ("PDF", (PDF_MAGIC,)),
    DocumentType.EMIRATES_ID_CARD: ("PNG or JPEG image", emirates_id.IMAGE_MAGIC),
    DocumentType.ASSETS_LIABILITIES: ("Excel (.xlsx) spreadsheet", (ZIP_MAGIC,)),
}
# The credit report is read first: its issue date is the as-of date for the resume (R4).
ORDER = (
    DocumentType.CREDIT_REPORT,
    DocumentType.BANK_STATEMENT,
    DocumentType.EMIRATES_ID_CARD,
    DocumentType.RESUME,
    DocumentType.ASSETS_LIABILITIES,
)


def _check_file(document_type: DocumentType, data: bytes) -> str | None:
    if not data:
        return "the file is empty"
    if len(data) > MAX_BYTES:
        return "the file is larger than 10 MB"
    kind, magic = EXPECTED_KIND[document_type]
    if not data.startswith(magic):
        return f"the file is not a {kind}"
    return None


def _extract(document_type: DocumentType, data: bytes, as_of: date, min_confidence: float):
    if document_type is DocumentType.BANK_STATEMENT:
        return bank_statement.parse(data)
    if document_type is DocumentType.CREDIT_REPORT:
        return credit_report.parse(data)
    if document_type is DocumentType.RESUME:
        return resume.parse(data, as_of)
    if document_type is DocumentType.EMIRATES_ID_CARD:
        return emirates_id.parse(data, min_confidence)
    return assets_liabilities.parse(data)


def extract_all(
    files: dict[DocumentType, bytes], min_confidence: float, today: date | None = None
) -> dict[DocumentType, ExtractedDocument]:
    """Read every document; a failure in one never stops the others (it becomes ``ok=False``).

    Results come back in ``DocumentType`` order. ``today`` is only the fallback as-of date for
    the resume when the credit report has no readable issue date.
    """
    results: dict[DocumentType, ExtractedDocument] = {}
    as_of = today or date.today()
    for document_type in ORDER:
        data = files[document_type]
        started = time.perf_counter()
        problem = _check_file(document_type, data)
        if problem:
            doc = ExtractedDocument(document_type, ok=False, error=problem)
        else:
            try:
                doc = _extract(document_type, data, as_of, min_confidence)
            except ExtractionError as exc:
                doc = ExtractedDocument(document_type, ok=False, error=str(exc))
            except Exception as exc:  # any parser failure routes to a human, never a crash
                doc = failed(
                    ExtractedDocument(document_type, ok=False),
                    f"the document could not be read ({type(exc).__name__})",
                )
        elapsed = int((time.perf_counter() - started) * 1000)
        results[document_type] = ExtractedDocument(
            doc.document_type, doc.ok, doc.fields, doc.items, doc.confidence, doc.error, elapsed
        )
        if document_type is DocumentType.CREDIT_REPORT and "report_date" in doc.fields:
            as_of = date.fromisoformat(doc.fields["report_date"])
    return {t: results[t] for t in DocumentType}
