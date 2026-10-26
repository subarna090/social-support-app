"""Emirates ID card image: name, ID number and date of birth by local OCR (research R2).

RapidOCR returns text lines with a confidence each. At the card's native size it drops spaces
between words ("OmarKhalidAl Mansoori"); doubling the image first fixes this on every demo card
at no real cost (measured 2026-10-26). Captions are still matched with spaces removed, and the
value is the next line. A required field read below ``min_confidence`` makes the card unreadable
(FR-016, Principle III).
"""

import io
import re
from functools import cache

from PIL import Image

from social_support.domain.documents import REQUIRED_FIELDS, DocumentType, ExtractedDocument
from social_support.extraction.common import failed, result
from social_support.extraction.pdf_text import ExtractionError

ID_NUMBER = re.compile(r"784\D?\d{4}\D?\d{7}\D?\d")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
CAPTIONS = {"name": "full_name", "idnumber": "emirates_id", "dateofbirth": "date_of_birth"}
IMAGE_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")
UPSCALE_BELOW_WIDTH = 2000  # smaller cards are doubled before OCR


@cache
def _engine():
    """Loaded once (about 1 s); later cards take about 3 s each on CPU."""
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _upscaled(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data))
    if image.width >= UPSCALE_BELOW_WIDTH:
        return data
    image = image.convert("RGB").resize((image.width * 2, image.height * 2), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _format_id(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    return f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14]}"


def parse_ocr_lines(lines: list[tuple[str, float]], min_confidence: float) -> ExtractedDocument:
    fields: dict[str, str] = {}
    confidence: dict[str, float] = {}
    for (caption, _), (value, score) in zip(lines, lines[1:], strict=False):
        name = CAPTIONS.get(re.sub(r"\s", "", caption).lower())
        if name and name not in fields:
            fields[name], confidence[name] = value.strip(), score
    # The ID number is distinctive enough to find anywhere, even if its caption was misread.
    for text, score in lines:
        if match := ID_NUMBER.search(text):
            fields["emirates_id"], confidence["emirates_id"] = _format_id(match.group()), score
            break
    # A caption followed by the wrong line (e.g. a missing value) must not be taken as the value.
    for name, pattern in (("emirates_id", ID_NUMBER), ("date_of_birth", DATE)):
        if name in fields and not pattern.fullmatch(fields[name]):
            del fields[name], confidence[name]

    doc = result(DocumentType.EMIRATES_ID_CARD, fields, confidence=confidence)
    low = [
        f
        for f in REQUIRED_FIELDS[DocumentType.EMIRATES_ID_CARD]
        if f in confidence and confidence[f] < min_confidence
    ]
    if doc.ok and low:
        return failed(doc, f"read with low confidence: {', '.join(low)}")
    return doc


def parse(data: bytes, min_confidence: float) -> ExtractedDocument:
    if not data.startswith(IMAGE_MAGIC):
        raise ExtractionError("the ID card must be a PNG or JPEG image")
    output, _ = _engine()(_upscaled(data))
    lines = [(text, float(score)) for _box, text, score in (output or [])]
    return parse_ocr_lines(lines, min_confidence)
