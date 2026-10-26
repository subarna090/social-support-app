"""Credit report: subject, score, active defaults and report date (research R1)."""

import re

from social_support.domain.documents import DocumentType, ExtractedDocument
from social_support.extraction.common import result
from social_support.extraction.pdf_text import pdf_text

ISSUED = re.compile(r"issued (\d{4}-\d{2}-\d{2})")
SCORE = re.compile(r"Score:\s*(\d{3})")
DEFAULTS = re.compile(r"Active defaults:\s*(\d+)")
# The subject table comes out one cell per line: a caption, then its value.
SUBJECT = {"Name": "full_name", "Emirates ID": "emirates_id", "Address on file": "address"}


def _subject(lines: list[str]) -> dict[str, str]:
    if "Subject" not in lines:
        return {}
    start = lines.index("Subject") + 1
    end = lines.index("Household members on file") if "Household members on file" in lines else None
    block = lines[start:end]
    fields: dict[str, str] = {}
    for caption, value in zip(block, block[1:], strict=False):
        if caption in SUBJECT and SUBJECT[caption] not in fields:
            fields[SUBJECT[caption]] = value
    return fields


def parse_text(text: str) -> ExtractedDocument:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    fields = _subject(lines)
    for name, pattern in (
        ("report_date", ISSUED),
        ("credit_score", SCORE),
        ("active_credit_defaults", DEFAULTS),
    ):
        if match := pattern.search(text):
            fields[name] = match.group(1)
    return result(DocumentType.CREDIT_REPORT, fields)


def parse(data: bytes) -> ExtractedDocument:
    return parse_text(pdf_text(data))
