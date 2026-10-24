"""T040: GET /api/v1/review-queue against contracts/api.md."""

import pytest

from tests.conftest import TEST_PASSCODE
from tests.fixtures.synthetic_applications import valid_payload

URL = "/api/v1/review-queue"
DENIED = {"detail": "Access denied."}


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Caseworker-Passcode": "wrong"}, {"X-Caseworker-Passcode": ""}],
    ids=["missing", "wrong", "empty"],
)
def test_401_without_the_right_passcode(client, headers):
    response = client.get(URL, headers=headers)
    assert response.status_code == 401
    assert response.json() == DENIED


def test_401_when_no_passcode_is_configured(make_client):
    client = make_client(caseworker_passcode=None)
    response = client.get(URL, headers={"X-Caseworker-Passcode": TEST_PASSCODE})
    assert response.status_code == 401
    assert response.json() == DENIED


def test_200_items_have_exactly_the_documented_fields(client):
    client.post(
        "/api/v1/applications", json=valid_payload(family_size=2, net_monthly_income_aed="4500")
    )
    response = client.get(URL, headers={"X-Caseworker-Passcode": TEST_PASSCODE})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert set(items[0]) == {"reference_number", "full_name", "submitted_at", "flag_reason"}
    assert items[0]["flag_reason"] == "borderline income"
    assert items[0]["submitted_at"].endswith("Z")
