"""T048: economic enablement over the API (US4, FR-012, FR-013, FR-017)."""

from sqlalchemy import select

from social_support.persistence.orm import DecisionRow, EnablementPlanRow, ProcessingTraceStepRow
from tests.conftest import FailingAdvisor, FakeAdvisor
from tests.fixtures.demo_upload import form_values, upload_pack


def _submit(client, pack):
    body = upload_pack(client, pack).json()
    return body, form_values(pack)["emirates_id"]


def _enablement(client, reference, emirates_id):
    return client.post(
        f"/api/v1/applications/{reference}/enablement", json={"emirates_id": emirates_id}
    )


def test_plan_comes_from_the_advisor_and_is_stored_with_its_profile(make_client, demo_packs):
    advisor = FakeAdvisor()
    client = make_client(advisor=advisor)
    body, eid = _submit(client, demo_packs["review"])

    response = _enablement(client, body["reference_number"], eid)
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["is_fallback"] is False and plan["model"] == "fake-model"
    assert plan["training"] == ["Advanced course building on Electrical maintenance"]
    assert plan["job_matches"] == ["Senior Technician roles"]

    (profile,) = advisor.profiles
    assert profile.skills[0] == "Electrical maintenance"
    assert (profile.outcome, profile.income_band, profile.family_size) == (
        "NEEDS_HUMAN_REVIEW",
        "borderline",
        4,
    )
    with client.app.state.sessionmaker() as session:
        row = session.scalar(select(EnablementPlanRow))
        assert row.profile == profile.as_dict()
        assert row.latency_ms >= 0 and row.error_type is None
        steps = session.scalars(select(ProcessingTraceStepRow.step)).all()
        assert steps[-1] == "ENABLEMENT"

    # A second request returns the stored plan without calling the model again.
    again = _enablement(client, body["reference_number"], eid).json()
    assert again == plan
    assert len(advisor.profiles) == 1


def test_profile_sent_to_the_model_has_no_identity_or_exact_income(make_client, demo_packs):
    advisor = FakeAdvisor()
    client = make_client(advisor=advisor)
    body, eid = _submit(client, demo_packs["review"])
    _enablement(client, body["reference_number"], eid)
    sent = str(advisor.profiles[0].as_dict())
    form = form_values(demo_packs["review"])
    for secret in (form["full_name"], "Al Zaabi", eid, "Al Waha Engineering", "9000", "7000"):
        assert secret not in sent


def test_failing_model_gives_the_labelled_fallback_and_keeps_the_decision(make_client, demo_packs):
    client = make_client(advisor=FailingAdvisor())
    body, eid = _submit(client, demo_packs["approve"])
    with client.app.state.sessionmaker() as session:
        before = session.scalar(select(DecisionRow)).outcome

    plan = _enablement(client, body["reference_number"], eid).json()
    assert plan["is_fallback"] is True and plan["model"] == "fallback"
    assert plan["training"] and plan["job_matches"] and plan["career_counselling"]
    with client.app.state.sessionmaker() as session:
        assert session.scalar(select(DecisionRow)).outcome == before == "APPROVE"
        row = session.scalar(select(EnablementPlanRow))
        assert row.error_type == "TimeoutError"


def test_unknown_reference_and_wrong_id_are_indistinguishable(client, demo_packs):
    body, eid = _submit(client, demo_packs["approve"])
    unknown = _enablement(client, "SSA-0000000000", eid)
    wrong_id = _enablement(client, body["reference_number"], "784-1990-1234567-1")
    assert unknown.status_code == wrong_id.status_code == 404
    assert unknown.json() == wrong_id.json()
