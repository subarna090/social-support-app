"""T041: caseworker review queue (US3, FR-012, Clarification Q3)."""

from tests.conftest import TEST_PASSCODE, FailingAssessor
from tests.fixtures.synthetic_applications import valid_payload

SUBMIT = "/api/v1/applications"
QUEUE = "/api/v1/review-queue"
AUTH = {"X-Caseworker-Passcode": TEST_PASSCODE}


def _submit(client, name: str, family: int, income: str) -> str:
    payload = valid_payload(full_name=name, family_size=family, net_monthly_income_aed=income)
    return client.post(SUBMIT, json=payload).json()["reference_number"]


def test_only_needs_human_review_items_newest_first(client):
    _submit(client, "Approve Case", 4, "6000")
    first_review = _submit(client, "Borderline One", 2, "4500")
    _submit(client, "Decline Case", 1, "3000")
    second_review = _submit(client, "Borderline Two", 1, "2000")

    items = client.get(QUEUE, headers=AUTH).json()["items"]
    assert [i["reference_number"] for i in items] == [second_review, first_review]
    assert [i["full_name"] for i in items] == ["Borderline Two", "Borderline One"]
    assert {i["flag_reason"] for i in items} == {"borderline income"}


def test_assessment_failures_appear_in_the_queue(make_client):
    client = make_client(assessor=FailingAssessor())
    reference = _submit(client, "Fallback Case", 4, "6000")
    items = client.get(QUEUE, headers=AUTH).json()["items"]
    assert [(i["reference_number"], i["flag_reason"]) for i in items] == [
        (reference, "automatic assessment unavailable")
    ]


def test_empty_queue(client):
    _submit(client, "Approve Case", 4, "6000")
    assert client.get(QUEUE, headers=AUTH).json() == {"items": []}


def test_fails_closed_without_configured_passcode(make_client):
    client = make_client(caseworker_passcode=None)
    _submit(client, "Borderline Case", 2, "4500")
    response = client.get(QUEUE, headers=AUTH)
    assert response.status_code == 401
    assert "Borderline Case" not in response.text


def test_wrong_passcode_reveals_no_data(client):
    _submit(client, "Borderline Case", 2, "4500")
    response = client.get(QUEUE, headers={"X-Caseworker-Passcode": "guess"})
    assert response.status_code == 401
    assert "Borderline Case" not in response.text
