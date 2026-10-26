"""T018: POST /api/v1/applications/with-documents against specs/004-poc-demo/contracts/api.md."""

import re

from tests.fixtures.demo_upload import upload_pack
from tests.fixtures.synthetic_applications import valid_payload

MONEY = re.compile(r"^\d+\.\d{2}$")
TIMESTAMP_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
DECISION_KEYS = {
    "outcome",
    "income_per_member_aed",
    "explanation",
    "suggested_next_steps",
    "flag_reason",
    "rule_version",
    "decided_at",
    "findings",
}


def test_201_has_the_documented_shape(client, demo_packs):
    response = upload_pack(client, demo_packs["approve"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "reference_number",
        "submitted_at",
        "previous_application_exists",
        "decision",
        "documents",
        "cross_checks",
    }
    assert set(body["decision"]) == DECISION_KEYS
    assert TIMESTAMP_UTC.fullmatch(body["decision"]["decided_at"])
    assert MONEY.fullmatch(body["decision"]["income_per_member_aed"])
    assert body["decision"]["rule_version"].startswith("decision/v1+")
    for finding in body["decision"]["findings"]:
        assert set(finding) == {"rule_id", "outcome", "text", "sources"}
    assert [d["document_type"] for d in body["documents"]] == [
        "BANK_STATEMENT",
        "EMIRATES_ID_CARD",
        "RESUME",
        "ASSETS_LIABILITIES",
        "CREDIT_REPORT",
    ]
    for document in body["documents"]:
        assert set(document) == {"document_type", "label", "ok", "error", "fields", "items"}
    for check in body["cross_checks"]:
        assert set(check) == {"check_id", "passed", "form_value", "document_value", "message"}


def test_422_names_the_missing_document(client, demo_packs):
    response = upload_pack(client, demo_packs["approve"], omit=("resume",))
    assert response.status_code == 422
    assert response.json() == {"errors": [{"field": "resume", "message": "Attach the resume."}]}


def test_422_for_invalid_form_fields_uses_the_flat_shape(client, demo_packs):
    response = upload_pack(client, demo_packs["approve"], family_size=0)
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == ["family_size"]


def test_json_submit_decision_also_has_findings(client):
    response = client.post("/api/v1/applications", json=valid_payload())
    assert response.status_code == 201
    assert response.json()["decision"]["findings"] == []


def test_protected_attribute_in_the_form_is_still_rejected(client, demo_packs):
    response = upload_pack(client, demo_packs["approve"], nationality="Emirati")
    assert response.status_code == 422
    assert response.json() == {
        "errors": [{"field": "nationality", "message": "This field is not accepted."}]
    }
