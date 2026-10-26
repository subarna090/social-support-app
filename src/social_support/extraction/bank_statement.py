"""Bank statement: account holder, average monthly income credits, closing balance (R1, R3)."""

import re
from decimal import Decimal

from social_support.domain.documents import DocumentType, ExtractedDocument
from social_support.extraction.common import money, result
from social_support.extraction.pdf_text import pdf_text

HOLDER = re.compile(r"^Account holder:\s*(.+?)\s*$", re.MULTILINE)
TOTALS = re.compile(
    r"Total credits:\s*([\d,]+\.\d{2})\s*AED\.\s*Closing balance:\s*(-?[\d,]+\.\d{2})"
)


def parse_text(text: str) -> ExtractedDocument:
    holder = HOLDER.search(text)
    totals = TOTALS.findall(text)  # one per statement month
    fields = {"account_holder": holder.group(1) if holder else ""}
    if totals:
        credits = [Decimal(money(c)) for c, _ in totals]
        fields["monthly_income_aed"] = money(sum(credits) / len(credits))
        fields["closing_balance_aed"] = money(totals[-1][1])
        fields["statement_months"] = str(len(totals))
    return result(DocumentType.BANK_STATEMENT, fields)


def parse(data: bytes) -> ExtractedDocument:
    return parse_text(pdf_text(data))
