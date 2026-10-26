"""T015: cross-checks between the form and the extracted documents (feature 004, FR-005)."""

from decimal import Decimal

import pytest

from social_support.domain.crosschecks import run_crosschecks
from social_support.domain.documents import DocumentType, ExtractedDocument

NAME = "Hassan Ali Al Zaabi"
EID = "784-1985-0000903-4"


def documents(
    card_name=NAME, card_id=EID, holder=NAME, bank_income="9000.00", card_ok=True, bank_ok=True
):
    return {
        DocumentType.EMIRATES_ID_CARD: ExtractedDocument(
            DocumentType.EMIRATES_ID_CARD,
            ok=card_ok,
            fields={"full_name": card_name, "emirates_id": card_id, "date_of_birth": "1985-11-05"},
        ),
        DocumentType.BANK_STATEMENT: ExtractedDocument(
            DocumentType.BANK_STATEMENT,
            ok=bank_ok,
            fields={"account_holder": holder, "monthly_income_aed": bank_income},
        ),
    }


def checks(declared="9000.00", tolerance="10", **doc_overrides):
    results = run_crosschecks(
        full_name=NAME,
        emirates_id=EID,
        declared_income_aed=Decimal(declared),
        documents=documents(**doc_overrides),
        tolerance_pct=Decimal(tolerance),
    )
    return {r.check_id: r for r in results}


def test_all_four_checks_run_and_pass_for_consistent_documents():
    results = checks()
    assert list(results) == [
        "name_vs_id_card",
        "emirates_id_vs_id_card",
        "name_vs_bank_holder",
        "income_vs_bank",
    ]
    assert all(r.passed for r in results.values())
    assert results["income_vs_bank"].sources == (DocumentType.BANK_STATEMENT,)


def test_names_compare_ignoring_case_and_whitespace():
    assert checks(card_name="  hassan ali  AL ZAABI ")["name_vs_id_card"].passed


def test_name_mismatch_fails_with_both_values():
    result = checks(card_name="Hasan Ali Al Zaabi")["name_vs_id_card"]
    assert result.passed is False
    assert (result.form_value, result.document_value) == (NAME, "Hasan Ali Al Zaabi")
    assert NAME in result.message and "Hasan Ali Al Zaabi" in result.message


def test_emirates_ids_compare_as_digits():
    assert checks(card_id="784198500009034")["emirates_id_vs_id_card"].passed
    assert checks(card_id="784-1985-0000903-5")["emirates_id_vs_id_card"].passed is False


def test_bank_holder_mismatch_fails():
    assert checks(holder="Someone Else")["name_vs_bank_holder"].passed is False


@pytest.mark.parametrize(
    ("declared", "passed"),
    [("8100.00", True), ("9900.00", True), ("8099.99", False), ("9900.01", False)],
)
def test_income_tolerance_is_ten_percent_of_bank_income(declared, passed):
    assert checks(declared=declared)["income_vs_bank"].passed is passed


def test_income_mismatch_message_names_both_amounts():
    result = checks(declared="7000.00")["income_vs_bank"]
    assert result.passed is False
    assert "7000.00" in result.message and "9000.00" in result.message and "10%" in result.message


def test_checks_are_skipped_when_a_document_could_not_be_read():
    results = checks(card_ok=False, bank_ok=False)
    assert {r.passed for r in results.values()} == {None}
