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


class FakeClient:
    response: dict | ApiError = APPROVED
    submitted: list[dict] = []

    def submit(self, payload: dict) -> dict:
        FakeClient.submitted.append(payload)
        if isinstance(self.response, ApiError):
            raise self.response
        return self.response


@pytest.fixture
def app(monkeypatch) -> AppTest:
    st.cache_resource.clear()
    FakeClient.response, FakeClient.submitted = APPROVED, []
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
