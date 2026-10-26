"""Cross-checks between the application form and the extracted documents (feature 004, FR-005).

Pure functions. Results carry identity values for the caseworker, so they are turned into
findings by the service and never handed to an assessor (research R6).
"""

import re
from decimal import Decimal

from social_support.domain.documents import CrossCheckResult, DocumentType, ExtractedDocument

CARD = DocumentType.EMIRATES_ID_CARD
BANK = DocumentType.BANK_STATEMENT


def _name_key(name: str) -> str:
    """Case- and whitespace-insensitive: OCR can drop the spaces between words."""
    return re.sub(r"\s", "", name).casefold()


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _skipped(check_id: str, form_value: str, source: DocumentType) -> CrossCheckResult:
    return CrossCheckResult(
        check_id,
        None,
        form_value,
        "",
        (source,),
        f"Not checked: the {source.label.lower()} could not be read.",
    )


def _names(check_id: str, form_name: str, doc: ExtractedDocument, field: str, what: str):
    if not doc.ok:
        return _skipped(check_id, form_name, doc.document_type)
    found = doc.fields[field]
    source = doc.document_type.label.lower()
    if _name_key(form_name) == _name_key(found):
        return CrossCheckResult(
            check_id, True, form_name, found, (doc.document_type,),
            f"The name on the form matches the {what} on the {source}.",
        )  # fmt: skip
    return CrossCheckResult(
        check_id, False, form_name, found, (doc.document_type,),
        f"The name on the form ({form_name}) does not match the {what} on the {source} ({found}).",
    )  # fmt: skip


def _emirates_id(form_id: str, card: ExtractedDocument) -> CrossCheckResult:
    check_id = "emirates_id_vs_id_card"
    if not card.ok:
        return _skipped(check_id, form_id, CARD)
    found = card.fields["emirates_id"]
    if _digits(form_id) == _digits(found):
        message = "The Emirates ID number on the form matches the ID card."
        return CrossCheckResult(check_id, True, form_id, found, (CARD,), message)
    message = (
        f"The Emirates ID number on the form ({form_id}) does not match the ID card ({found})."
    )
    return CrossCheckResult(check_id, False, form_id, found, (CARD,), message)


def _income(declared: Decimal, bank: ExtractedDocument, tolerance_pct: Decimal):
    check_id = "income_vs_bank"
    form_value = f"{declared:.2f}"
    if not bank.ok:
        return _skipped(check_id, form_value, BANK)
    found = Decimal(bank.fields["monthly_income_aed"])
    allowed = found * tolerance_pct / 100
    tolerance = f"{tolerance_pct.normalize():f}%"
    if abs(declared - found) <= allowed:
        message = (
            f"Declared income of {form_value} AED is within {tolerance} of the bank statement "
            f"income of {found:.2f} AED."
        )
        return CrossCheckResult(check_id, True, form_value, f"{found:.2f}", (BANK,), message)
    message = (
        f"Declared income of {form_value} AED differs from the bank statement income of "
        f"{found:.2f} AED by more than {tolerance}."
    )
    return CrossCheckResult(check_id, False, form_value, f"{found:.2f}", (BANK,), message)


def run_crosschecks(
    *,
    full_name: str,
    emirates_id: str,
    declared_income_aed: Decimal,
    documents: dict[DocumentType, ExtractedDocument],
    tolerance_pct: Decimal,
) -> list[CrossCheckResult]:
    card, bank = documents[CARD], documents[BANK]
    return [
        _names("name_vs_id_card", full_name, card, "full_name", "name"),
        _emirates_id(emirates_id, card),
        _names("name_vs_bank_holder", full_name, bank, "account_holder", "account holder"),
        _income(declared_income_aed, bank, tolerance_pct),
    ]
