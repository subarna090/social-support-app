"""T017: extraction of all three demo packs matches their answer keys (SC-003, real OCR)."""

import json
from decimal import Decimal

import pytest

from social_support.domain.documents import DocumentType
from social_support.extraction import extract_all

FILES = {
    DocumentType.BANK_STATEMENT: "bank_statement.pdf",
    DocumentType.EMIRATES_ID_CARD: "emirates_id.png",
    DocumentType.RESUME: "resume.pdf",
    DocumentType.ASSETS_LIABILITIES: "assets_liabilities.xlsx",
    DocumentType.CREDIT_REPORT: "credit_report.pdf",
}


@pytest.fixture(scope="module", params=["approve", "soft_decline", "review"])
def extracted(request, demo_packs):
    pack = demo_packs[request.param]
    key = json.loads((pack / "answer_key.json").read_text(encoding="utf-8"))
    files = {t: (pack / name).read_bytes() for t, name in FILES.items()}
    return extract_all(files, min_confidence=0.80), key


def test_every_document_is_read(extracted):
    documents, _ = extracted
    assert {t: d.ok for t, d in documents.items()} == {t: True for t in FILES}
    assert all(d.duration_ms >= 0 for d in documents.values())


def test_values_match_the_answer_key(extracted):
    documents, key = extracted
    views, facts = key["documents"], key["facts"]
    bank = documents[DocumentType.BANK_STATEMENT].fields
    assert bank["account_holder"] == views["bank_statement"]["account_holder"]
    assert Decimal(bank["monthly_income_aed"]) == Decimal(
        views["bank_statement"]["monthly_income_credits_aed"]
    )

    card = documents[DocumentType.EMIRATES_ID_CARD].fields
    for field in ("full_name", "emirates_id", "date_of_birth"):
        assert card[field] == views["emirates_id"][field]

    resume = documents[DocumentType.RESUME]
    assert int(resume.fields["months_employed_last_24"]) == facts["months_employed_last_24"]
    assert resume.items["skills"] == tuple(views["resume"]["skills"])

    assets = documents[DocumentType.ASSETS_LIABILITIES].fields
    assert Decimal(assets["total_assets_aed"]) == Decimal(facts["total_assets_aed"])
    assert Decimal(assets["total_liabilities_aed"]) == Decimal(facts["total_liabilities_aed"])

    credit = documents[DocumentType.CREDIT_REPORT].fields
    assert int(credit["credit_score"]) == facts["credit_score"]
    assert int(credit["active_credit_defaults"]) == facts["active_credit_defaults"]
    assert credit["report_date"] == views["credit_report"]["report_date"]
