"""T033: POST /api/v1/applications/lookup against contracts/api.md."""

from tests.fixtures.synthetic_applications import valid_payload

SUBMIT = "/api/v1/applications"
LOOKUP = "/api/v1/applications/lookup"
NOT_FOUND = {"detail": "No application found for the details provided."}


def _submit(client, **overrides) -> dict:
    return client.post(SUBMIT, json=valid_payload(**overrides)).json()


def test_200_has_application_and_decision_blocks(client):
    submitted = _submit(client)
    response = client.post(
        LOOKUP,
        json={
            "reference_number": submitted["reference_number"],
            "emirates_id": "784-1990-1234567-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "reference_number",
        "submitted_at",
        "previous_application_exists",
        "application",
        "decision",
    }
    assert body["application"] == {
        "full_name": "Aisha Al Mansoori",
        "emirates_id": "784-1990-1234567-1",
        "family_size": 4,
        "net_monthly_income_aed": "6000.00",
        "employment_status": "EMPLOYED",
    }
    assert body["decision"] == submitted["decision"]


def test_404_is_byte_identical_for_unknown_reference_and_mismatched_id(client):
    submitted = _submit(client)
    unknown = client.post(
        LOOKUP, json={"reference_number": "SSA-0000000000", "emirates_id": "784-1990-1234567-1"}
    )
    mismatched = client.post(
        LOOKUP,
        json={
            "reference_number": submitted["reference_number"],
            "emirates_id": "784-1991-7654321-2",
        },
    )
    assert unknown.status_code == mismatched.status_code == 404
    assert unknown.content == mismatched.content
    assert unknown.json() == NOT_FOUND
