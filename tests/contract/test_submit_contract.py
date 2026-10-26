"""T022: POST /api/v1/applications against contracts/api.md."""

import re

from tests.fixtures.synthetic_applications import valid_payload

URL = "/api/v1/applications"
MONEY = re.compile(r"^\d+\.\d{2}$")
TIMESTAMP_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _contains_key(obj, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj or any(_contains_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_key(v, key) for v in obj)
    return False


def test_201_has_exactly_the_documented_shape(client):
    response = client.post(URL, json=valid_payload())
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "reference_number",
        "submitted_at",
        "previous_application_exists",
        "decision",
    }
    assert set(body["decision"]) == {
        "outcome",
        "income_per_member_aed",
        "explanation",
        "suggested_next_steps",
        "flag_reason",
        "rule_version",
        "decided_at",
        "findings",  # feature 004: always present, empty for the placeholder rule
    }
    assert body["decision"]["outcome"] == "APPROVE"
    assert body["decision"]["income_per_member_aed"] == "1500.00"
    assert MONEY.fullmatch(body["decision"]["income_per_member_aed"])
    assert TIMESTAMP_UTC.fullmatch(body["submitted_at"])
    assert TIMESTAMP_UTC.fullmatch(body["decision"]["decided_at"])
    assert body["previous_application_exists"] is False
    assert not _contains_key(body, "id")


def test_422_has_flat_errors_with_one_entry_per_invalid_field(client):
    payload = valid_payload(emirates_id="123-45", family_size=0)
    response = client.post(URL, json=payload)
    assert response.status_code == 422
    errors = response.json()["errors"]
    assert sorted(e["field"] for e in errors) == ["emirates_id", "family_size"]
    assert {e["field"]: e["message"] for e in errors} == {
        "emirates_id": "Emirates ID must be 15 digits in the format 784-YYYY-NNNNNNN-N.",
        "family_size": "Family size must be a whole number from 1 to 20.",
    }


def test_protected_attribute_is_rejected(client):
    response = client.post(URL, json=valid_payload(nationality="Emirati"))
    assert response.status_code == 422
    assert [e["field"] for e in response.json()["errors"]] == ["nationality"]


def test_no_update_or_delete_routes_for_applications(client):
    # The OpenAPI schema lists every public endpoint (app.routes hides included routers).
    paths = {p: ops for p, ops in client.app.openapi()["paths"].items() if p.startswith(URL)}
    assert URL in paths  # guard against passing vacuously
    for path, operations in paths.items():
        assert not set(operations) & {"put", "patch", "delete"}, path
