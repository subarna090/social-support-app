"""Helpers shared by the parsers: canonical money and the ``ExtractedDocument`` result."""

from decimal import ROUND_HALF_UP, Decimal

from social_support.domain.documents import DocumentType, ExtractedDocument

CENT = Decimal("0.01")


def money(text: str | Decimal | float) -> str:
    """``"1,234.5"`` -> ``"1234.50"`` (2 dp, half up)."""
    value = Decimal(str(text).replace(",", "").strip())
    return f"{value.quantize(CENT, rounding=ROUND_HALF_UP):.2f}"


def result(
    document_type: DocumentType,
    fields: dict[str, str],
    items: dict[str, tuple[str, ...]] | None = None,
    confidence: dict[str, float] | None = None,
) -> ExtractedDocument:
    """Usable only when every required field was found; otherwise name the missing ones."""
    doc = ExtractedDocument(
        document_type,
        ok=True,
        fields={k: v for k, v in fields.items() if v},
        items=items or {},
        confidence=confidence or {},
    )
    if doc.missing_fields:
        return failed(doc, f"required values not found: {', '.join(doc.missing_fields)}")
    return doc


def failed(doc: ExtractedDocument, error: str) -> ExtractedDocument:
    return ExtractedDocument(
        doc.document_type, False, doc.fields, doc.items, doc.confidence, error, doc.duration_ms
    )
