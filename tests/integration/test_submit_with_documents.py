"""T032, T036, T038, T042: submitting the demo packs with their documents (feature 004)."""

import hashlib
import logging

import pytest
from sqlalchemy import select

from social_support.persistence.orm import (
    ApplicationRow,
    CrossCheckRow,
    DecisionInputsRow,
    DocumentRow,
    FindingRow,
    ProcessingTraceStepRow,
)
from tests.conftest import TEST_PASSCODE
from tests.fixtures.broken_files import broken_files
from tests.fixtures.demo_upload import UPLOADS, form_values, upload_pack


def rule_ids(body):
    return [f["rule_id"] for f in body["decision"]["findings"]]


# --- US1 ----------------------------------------------------------------------------------------


def test_approve_pack_is_approved_and_everything_is_stored(client, demo_packs, caplog):
    caplog.set_level(logging.INFO, logger="social_support")
    response = upload_pack(client, demo_packs["approve"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["decision"]["outcome"] == "APPROVE"
    assert body["decision"]["income_per_member_aed"] == "1200.00"
    assert rule_ids(body) == [
        "income_within_band",
        "wealth_within_limit",
        "credit_good_standing",
        "stable_work",
    ]
    assert all(c["passed"] for c in body["cross_checks"])
    assert all(d["ok"] for d in body["documents"])

    settings = client.app.state.settings
    with client.app.state.sessionmaker() as session:
        app_row = session.scalar(select(ApplicationRow))
        documents = session.scalars(select(DocumentRow)).all()
        assert len(documents) == 5
        assert all(d.duration_ms >= 0 and d.ok for d in documents)
        for doc in documents:
            stored = (settings.upload_dir / doc.stored_path).read_bytes()
            assert hashlib.sha256(stored).hexdigest() == doc.sha256
        assert len(session.scalars(select(CrossCheckRow)).all()) == 4
        inputs = session.scalar(select(DecisionInputsRow))
        assert inputs.facts["income_per_member_aed"] == "1200.00"
        assert inputs.facts["net_wealth_aed"] == "30000.00"
        assert len(session.scalars(select(FindingRow)).all()) == 4
        steps = session.scalars(
            select(ProcessingTraceStepRow).where(
                ProcessingTraceStepRow.application_id == app_row.id
            )
        ).all()
        assert [s.step for s in steps] == [
            "RECEIVED",
            "VALIDATED",
            "EXTRACTED",
            "CROSS_CHECKED",
            "ASSESSED",
            "STORED",
            "RESULT_RETURNED",
        ]
        assert "EMIRATES_ID_CARD ok" in steps[2].detail

    form = form_values(demo_packs["approve"])
    for secret in (form["full_name"], form["emirates_id"], form["net_monthly_income_aed"]):
        assert secret not in caplog.text


def test_lookup_returns_the_findings(client, demo_packs):
    body = upload_pack(client, demo_packs["approve"]).json()
    form = form_values(demo_packs["approve"])
    found = client.post(
        "/api/v1/applications/lookup",
        json={"reference_number": body["reference_number"], "emirates_id": form["emirates_id"]},
    ).json()
    assert found["decision"]["findings"] == body["decision"]["findings"]


# --- US2 ----------------------------------------------------------------------------------------


def test_soft_decline_pack_names_both_failing_factors(client, demo_packs):
    body = upload_pack(client, demo_packs["soft_decline"]).json()
    assert body["decision"]["outcome"] == "SOFT_DECLINE"
    assert {"income_above_band", "high_net_wealth"} <= set(rule_ids(body))
    assert body["decision"]["suggested_next_steps"]
    assert all(c["passed"] for c in body["cross_checks"])


# --- US3 ----------------------------------------------------------------------------------------


def test_review_pack_names_borderline_income_and_the_income_mismatch(client, demo_packs):
    body = upload_pack(client, demo_packs["review"]).json()
    assert body["decision"]["outcome"] == "NEEDS_HUMAN_REVIEW"
    assert {"borderline_income", "crosscheck:income_vs_bank"} <= set(rule_ids(body))
    mismatch = next(
        f for f in body["decision"]["findings"] if f["rule_id"] == "crosscheck:income_vs_bank"
    )
    assert "7000.00" in mismatch["text"] and "9000.00" in mismatch["text"]
    assert mismatch["sources"] == ["Application form", "Bank statement"]

    queue = client.get("/api/v1/review-queue", headers={"X-Caseworker-Passcode": TEST_PASSCODE})
    (item,) = queue.json()["items"]
    assert item["reference_number"] == body["reference_number"]
    assert any("borderline" in r for r in item["reasons"])
    assert any("7000.00" in r for r in item["reasons"])


def test_name_typed_differently_on_the_form_goes_to_review(client, demo_packs):
    body = upload_pack(client, demo_packs["approve"], full_name="Mariam Saeed Al Hamadi").json()
    assert body["decision"]["outcome"] == "NEEDS_HUMAN_REVIEW"
    assert {"crosscheck:name_vs_id_card", "crosscheck:name_vs_bank_holder"} <= set(rule_ids(body))


@pytest.mark.parametrize("case", ["empty", "truncated_pdf", "pdf_as_id_card", "over_10_mb"])
def test_broken_file_is_stored_and_routed_to_review(client, demo_packs, case):
    field, replacement = broken_files(demo_packs["approve"])[case]
    response = upload_pack(client, demo_packs["approve"], replace=replacement)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["decision"]["outcome"] == "NEEDS_HUMAN_REVIEW"
    document = next(d for d in body["documents"] if d["document_type"].lower() == field)
    assert not document["ok"] and document["error"]
    assert f"document:{document['document_type']}" in rule_ids(body)
    assert len(UPLOADS) == len(body["documents"])
