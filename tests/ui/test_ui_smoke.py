"""T025: Streamlit UI smoke test with a fake API client (no server needed)."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import social_support.ui.client as client_module
from social_support.ui.client import ApiError

APP = Path(__file__).resolve().parents[2] / "src" / "social_support" / "ui" / "app.py"

APPROVED = {
    "reference_number": "SSA-7K2M9QXH4D",
    "submitted_at": "2026-10-23T10:15:02Z",
    "previous_application_exists": False,
    "decision": {
        "outcome": "APPROVE",
        "income_per_member_aed": "1500.00",
        "explanation": "Net monthly household income of 6000.00 AED across 4 members gives "
        "1500.00 AED per member, which is below the 2000.00 AED support threshold.",
        "suggested_next_steps": [],
        "flag_reason": None,
        "rule_version": "income-per-member/v0.1+3fa2c1d9",
        "decided_at": "2026-10-23T10:15:02Z",
    },
}


APPLICATION = {
    "full_name": "Aisha Al Mansoori",
    "emirates_id": "784-1990-1234567-1",
    "family_size": 4,
    "net_monthly_income_aed": "6000.00",
    "employment_status": "EMPLOYED",
}


class FakeClient:
    response: dict | ApiError = APPROVED
    submitted: list[dict] = []

    lookup_response: dict | ApiError = APPROVED
    review_response: dict | ApiError = {"items": []}

    def review_queue(self, passcode: str) -> dict:
        if isinstance(self.review_response, ApiError):
            raise self.review_response
        return self.review_response

    def lookup(self, reference_number: str, emirates_id: str) -> dict:
        if isinstance(self.lookup_response, ApiError):
            raise self.lookup_response
        return self.lookup_response

    def submit(self, payload: dict) -> dict:
        FakeClient.submitted.append(payload)
        if isinstance(self.response, ApiError):
            raise self.response
        return self.response


@pytest.fixture
def app(monkeypatch) -> AppTest:
    st.cache_resource.clear()
    FakeClient.response, FakeClient.submitted = APPROVED, []
    FakeClient.lookup_response = APPROVED | {"application": APPLICATION}
    FakeClient.review_response = {"items": []}
    monkeypatch.setattr(client_module, "ApiClient", FakeClient)
    return AppTest.from_file(str(APP), default_timeout=30).run()


def _texts(at: AppTest) -> str:
    groups = (at.markdown, at.caption, at.success, at.warning, at.info, at.error)
    return "\n".join(str(e.value) for group in groups for e in group)


def _fill(at: AppTest) -> None:
    at.text_input(key="full_name").input("Aisha Al Mansoori")
    at.text_input(key="emirates_id").input("784-1990-1234567-1")
    at.number_input(key="family_size").set_value(4)
    at.number_input(key="net_monthly_income_aed").set_value(6000.0)
    at.selectbox(key="employment_status").select("EMPLOYED")


def test_apply_tab_renders_all_fields_and_income_help(app):
    assert not app.exception
    for key in ("full_name", "emirates_id"):
        assert app.text_input(key=key)
    assert app.number_input(key="family_size")
    assert app.selectbox(key="employment_status")
    assert "Net (take-home)" in app.number_input(key="net_monthly_income_aed").help
    # FR-001: the definition is visible on the form, not only in the tooltip (T052)
    assert any("Net (take-home)" in str(c.value) for c in app.caption)


def test_submit_shows_outcome_explanation_and_reference(app):
    _fill(app)
    app.button[0].click().run()
    assert not app.exception
    assert FakeClient.submitted[-1]["net_monthly_income_aed"] == "6000.00"
    text = _texts(app)
    for fragment in ("Approve", "1500.00 AED per member", "SSA-7K2M9QXH4D"):
        assert fragment in text


def test_validation_errors_are_shown_per_field(app):
    FakeClient.response = ApiError(
        422,
        "Validation failed",
        {"emirates_id": "Emirates ID must be 15 digits in the format 784-YYYY-NNNNNNN-N."},
    )
    _fill(app)
    app.button[0].click().run()
    assert not app.exception
    assert "Emirates ID must be 15 digits" in _texts(app)


def _look_up(at: AppTest) -> None:
    at.text_input(key="lookup_reference").input("SSA-7K2M9QXH4D")
    at.text_input(key="lookup_emirates_id").input("784-1990-1234567-1")
    next(b for b in at.button if b.label == "Look up").click().run()


def test_lookup_shows_details_decision_and_rule_version(app):
    _look_up(app)
    assert not app.exception
    text = _texts(app)
    for fragment in (
        "Aisha Al Mansoori",
        "6000.00 AED",
        "Approve",
        "income-per-member/v0.1+3fa2c1d9",
    ):
        assert fragment in text


def test_lookup_not_found_message(app):
    FakeClient.lookup_response = ApiError(404, "No application found for the details provided.")
    _look_up(app)
    assert "No application found for the details provided." in _texts(app)


def _open_review(at: AppTest) -> None:
    at.text_input(key="review_passcode").input("secret")
    next(b for b in at.button if b.label == "Show review queue").click().run()


def test_review_queue_lists_items(app):
    FakeClient.review_response = {
        "items": [
            {
                "reference_number": "SSA-Q4M8ZK2R1C",
                "full_name": "Omar Haddad",
                "submitted_at": "2026-10-23T10:20:44Z",
                "flag_reason": "borderline income",
            }
        ]
    }
    _open_review(app)
    assert not app.exception
    table = app.table[0].value
    assert list(table["Reference"]) == ["SSA-Q4M8ZK2R1C"]
    assert list(table["Flag reason"]) == ["borderline income"]


def test_review_queue_empty_state(app):
    _open_review(app)
    assert "No applications are waiting for review." in _texts(app)


def test_review_queue_access_denied(app):
    FakeClient.review_response = ApiError(401, "Access denied.")
    _open_review(app)
    assert "Access denied." in _texts(app)
    assert not app.table
