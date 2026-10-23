"""T034: lookup by reference number plus matching Emirates ID (US2, FR-011, SC-004)."""

import logging

import pytest

from social_support.services.tracing import JsonFormatter
from tests.conftest import FailingAssessor
from tests.fixtures.synthetic_applications import VALID_CASES

SUBMIT = "/api/v1/applications"
LOOKUP = "/api/v1/applications/lookup"


@pytest.mark.parametrize("id_format", ["dashed", "undashed"])
@pytest.mark.parametrize(("payload", "_expected"), VALID_CASES[:6])
def test_lookup_returns_exactly_what_was_shown_at_submission(client, payload, _expected, id_format):
    submitted = client.post(SUBMIT, json=payload).json()
    emirates_id = payload["emirates_id"]
    if id_format == "undashed":
        emirates_id = emirates_id.replace("-", "")

    found = client.post(
        LOOKUP, json={"reference_number": submitted["reference_number"], "emirates_id": emirates_id}
    )
    assert found.status_code == 200
    body = found.json()
    for key in ("reference_number", "submitted_at", "previous_application_exists", "decision"):
        assert body[key] == submitted[key]
    assert body["application"]["emirates_id"] == payload["emirates_id"]


def test_fallback_decision_is_retrievable_unchanged(make_client):
    client = make_client(assessor=FailingAssessor())
    payload = VALID_CASES[0][0]
    submitted = client.post(SUBMIT, json=payload).json()
    body = client.post(
        LOOKUP,
        json={
            "reference_number": submitted["reference_number"],
            "emirates_id": payload["emirates_id"],
        },
    ).json()
    assert body["decision"] == submitted["decision"]
    assert body["decision"]["rule_version"] == "fallback"


def test_mismatched_id_and_unknown_reference_both_return_404(client):
    payload = VALID_CASES[0][0]
    reference = client.post(SUBMIT, json=payload).json()["reference_number"]
    other_id = VALID_CASES[1][0]["emirates_id"]

    assert (
        client.post(
            LOOKUP, json={"reference_number": reference, "emirates_id": other_id}
        ).status_code
        == 404
    )
    assert (
        client.post(
            LOOKUP,
            json={"reference_number": "SSA-ZZZZZZZZZZ", "emirates_id": payload["emirates_id"]},
        ).status_code
        == 404
    )


def test_emirates_id_never_appears_in_urls_or_logs(client, caplog):
    caplog.set_level(logging.INFO, logger="social_support")
    payload = VALID_CASES[0][0]
    reference = client.post(SUBMIT, json=payload).json()["reference_number"]
    client.post(LOOKUP, json={"reference_number": reference, "emirates_id": payload["emirates_id"]})
    client.post(LOOKUP, json={"reference_number": reference, "emirates_id": "784-1991-7654321-2"})

    # The lookup route takes everything in the body: no path or query parameters.
    operations = client.app.openapi()["paths"][LOOKUP]
    assert set(operations) == {"post"}
    assert not operations["post"].get("parameters")
    assert "requestBody" in operations["post"]

    output = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    assert reference in output
    for secret in (payload["emirates_id"], payload["emirates_id"].replace("-", ""), "784-1991"):
        assert secret not in output
