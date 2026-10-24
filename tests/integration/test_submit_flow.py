"""T024: the full submission path against a real (in-memory or file) database."""

import json
import logging
import time
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from social_support.persistence.orm import ApplicationRow, DecisionRow
from social_support.services.tracing import JsonFormatter
from tests.conftest import FailingAssessor
from tests.fixtures.synthetic_applications import INVALID_CASES, VALID_CASES, valid_payload

URL = "/api/v1/applications"


def _application(client, reference: str) -> ApplicationRow:
    with client.app.state.sessionmaker() as session:
        row = session.scalar(
            select(ApplicationRow).where(ApplicationRow.reference_number == reference)
        )
        _ = row.decision, row.trace_steps  # load relationships before the session closes
        return row


def _count_applications(client) -> int:
    with client.app.state.sessionmaker() as session:
        return session.scalar(select(func.count()).select_from(ApplicationRow))


@pytest.mark.parametrize(("payload", "expected"), VALID_CASES)
def test_synthetic_cases_get_the_predicted_outcome(client, payload, expected):  # SC-005
    response = client.post(URL, json=payload)
    assert response.status_code == 201
    decision = response.json()["decision"]
    assert decision["outcome"] == expected.value
    assert decision["income_per_member_aed"] in decision["explanation"]
    assert decision["rule_version"] in decision["explanation"]


@pytest.mark.parametrize(("payload", "field"), INVALID_CASES)
def test_invalid_submissions_are_rejected_and_not_stored(client, payload, field):  # SC-006
    response = client.post(URL, json=payload)
    assert response.status_code == 422
    assert field in [e["field"] for e in response.json()["errors"]]
    assert _count_applications(client) == 0


def test_decision_and_trace_are_stored_in_order(client):
    reference = client.post(URL, json=valid_payload()).json()["reference_number"]
    row = _application(client, reference)
    assert row.decision.outcome == "APPROVE"
    assert row.decision.income_per_member_aed == Decimal("1500.00")
    assert [(s.sequence, s.step, s.status) for s in row.trace_steps] == [
        (1, "RECEIVED", "OK"),
        (2, "VALIDATED", "OK"),
        (3, "ASSESSED", "OK"),
        (4, "STORED", "OK"),
        (5, "RESULT_RETURNED", "OK"),
    ]


def test_assessment_failure_routes_to_human_review(make_client):  # FR-015
    client = make_client(assessor=FailingAssessor())
    response = client.post(URL, json=valid_payload())
    assert response.status_code == 201
    decision = response.json()["decision"]
    assert decision["outcome"] == "NEEDS_HUMAN_REVIEW"
    assert decision["flag_reason"] == "automatic assessment unavailable"
    assert decision["rule_version"] == "fallback"
    assert decision["income_per_member_aed"] is None
    assert "caseworker" in decision["explanation"]

    row = _application(client, response.json()["reference_number"])
    assessed = next(s for s in row.trace_steps if s.step == "ASSESSED")
    assert (assessed.status, assessed.detail) == ("FAILED", "RuntimeError")


def test_duplicate_emirates_id_is_accepted_and_noted(client):  # FR-017
    first = client.post(URL, json=valid_payload(family_size=4, net_monthly_income_aed="6000"))
    second = client.post(URL, json=valid_payload(family_size=1, net_monthly_income_aed="3000"))
    assert first.json()["previous_application_exists"] is False
    assert second.status_code == 201
    assert second.json()["previous_application_exists"] is True
    assert second.json()["decision"]["outcome"] == "SOFT_DECLINE"  # rule only
    assert first.json()["reference_number"] not in second.text
    assert _count_applications(client) == 2


def test_rule_change_creates_new_version_and_keeps_old_decisions(make_client, tmp_path):  # FR-013
    db_url = f"sqlite:///{(tmp_path / 'app.db').as_posix()}"
    old_client = make_client(database_url=db_url)
    old = old_client.post(URL, json=valid_payload()).json()

    new_client = make_client(database_url=db_url, rule_threshold_aed=Decimal("1800"))
    new = new_client.post(URL, json=valid_payload(emirates_id="784-1991-7654321-2")).json()

    assert new["decision"]["rule_version"] != old["decision"]["rule_version"]
    with new_client.app.state.sessionmaker() as session:
        versions = dict(session.execute(select(DecisionRow.id, DecisionRow.rule_version_id)).all())
    assert sorted(versions.values()) == sorted(
        [old["decision"]["rule_version"], new["decision"]["rule_version"]]
    )


def test_logs_contain_reference_but_no_emirates_id_or_income(client, caplog):  # Principle I
    caplog.set_level(logging.INFO, logger="social_support")
    payload = valid_payload(emirates_id="784-1985-7654321-9", net_monthly_income_aed="7345.67")
    reference = client.post(URL, json=payload).json()["reference_number"]

    formatter = JsonFormatter()
    lines = [formatter.format(r) for r in caplog.records if r.name.startswith("social_support")]
    output = "\n".join(lines)
    assert reference in output
    for secret in ("784-1985-7654321-9", "784198576543219", "7345.67", "Aisha"):
        assert secret not in output
    assert all(json.loads(line) for line in lines)


def test_95th_percentile_response_time_under_5_seconds(client):  # SC-002
    durations = []
    for payload, _ in VALID_CASES:
        start = time.perf_counter()
        assert client.post(URL, json=payload).status_code == 201
        durations.append(time.perf_counter() - start)
    durations.sort()
    p95 = durations[int(0.95 * (len(durations) - 1))]
    assert p95 < 5.0


def test_rejected_submission_logs_field_names_but_no_values(client, caplog):  # data-model.md
    caplog.set_level(logging.INFO, logger="social_support")
    payload = valid_payload(full_name="Zubair Secretname", emirates_id="123-45", family_size=0)
    assert client.post(URL, json=payload).status_code == 422

    records = [r for r in caplog.records if r.name.startswith("social_support")]
    rejected = [r for r in records if getattr(r, "status", None) == "rejected"]
    assert len(rejected) == 1
    entry = json.loads(JsonFormatter().format(rejected[0]))
    assert entry["fields"] == ["emirates_id", "family_size"]
    output = "\n".join(JsonFormatter().format(r) for r in records)
    for secret in ("123-45", "Zubair", "Secretname"):
        assert secret not in output
