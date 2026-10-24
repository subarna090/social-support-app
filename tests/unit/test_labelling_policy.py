"""T004: labelling policy v1 against contracts/labelling-policy.md and research R3 (test-first)."""

import re
from decimal import Decimal

import pytest

from social_support.domain.models import EmploymentStatus, Outcome
from social_support.labelling import HouseholdFacts, PolicyError, load_policy

POLICY_FILE = (
    __import__("importlib.resources", fromlist=["files"]).files("social_support.labelling")
    / "policies"
    / "eligibility_v1.toml"
)


def facts(**overrides) -> HouseholdFacts:
    """Neutral facts that land on ``low_income_stable_work``; override one factor per test."""
    values = {
        "family_size": 1,
        "net_monthly_income_aed": Decimal("1000.00"),
        "employment_status": EmploymentStatus.EMPLOYED,
        "months_employed_last_24": 24,
        "total_assets_aed": Decimal("10000.00"),
        "total_liabilities_aed": Decimal("0.00"),
        "credit_score": 700,
        "active_credit_defaults": 0,
    }
    values.update(overrides)
    return HouseholdFacts.build(**values)


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def label(policy, **overrides):
    return policy.evaluate(facts(**overrides))


# --- one boundary pair per rule --------------------------------------------------------------


def test_neutral_facts_are_approved_for_stable_work(policy):
    result = label(policy)
    assert (result.outcome, result.rule_id) == (Outcome.APPROVE, "low_income_stable_work")


def test_high_net_wealth_boundary(policy):
    assert label(policy, total_assets_aed=Decimal("500000.00")).rule_id != "high_net_wealth"
    result = label(policy, total_assets_aed=Decimal("500000.01"))
    assert (result.outcome, result.rule_id) == (Outcome.SOFT_DECLINE, "high_net_wealth")


def test_income_above_band_boundary(policy):
    at = label(policy, net_monthly_income_aed=Decimal("2500.00"))
    assert (at.outcome, at.rule_id) == (Outcome.NEEDS_HUMAN_REVIEW, "borderline_income")
    above = label(policy, net_monthly_income_aed=Decimal("2500.01"))
    assert (above.outcome, above.rule_id) == (Outcome.SOFT_DECLINE, "income_above_band")


def test_active_credit_defaults_boundary(policy):
    assert label(policy, active_credit_defaults=0).rule_id == "low_income_stable_work"
    result = label(policy, active_credit_defaults=1)
    assert (result.outcome, result.rule_id) == (
        Outcome.NEEDS_HUMAN_REVIEW,
        "active_credit_defaults",
    )


def test_poor_credit_score_boundary(policy):
    assert label(policy, credit_score=550).rule_id == "low_income_stable_work"
    result = label(policy, credit_score=549)
    assert (result.outcome, result.rule_id) == (Outcome.NEEDS_HUMAN_REVIEW, "poor_credit_score")


def test_borderline_income_boundary(policy):
    assert label(policy, net_monthly_income_aed=Decimal("1999.99")).outcome is Outcome.APPROVE
    result = label(policy, net_monthly_income_aed=Decimal("2000.00"))
    assert (result.outcome, result.rule_id) == (Outcome.NEEDS_HUMAN_REVIEW, "borderline_income")


@pytest.mark.parametrize(
    "status", [EmploymentStatus.UNEMPLOYED, EmploymentStatus.STUDENT, EmploymentStatus.RETIRED]
)
def test_low_income_not_in_work_is_approved(policy, status):
    result = label(policy, employment_status=status, months_employed_last_24=0)
    assert (result.outcome, result.rule_id) == (Outcome.APPROVE, "low_income_not_in_work")


def test_employed_with_no_recent_work_is_not_covered_by_not_in_work_rule(policy):
    result = label(policy, employment_status=EmploymentStatus.EMPLOYED, months_employed_last_24=0)
    assert result.rule_id != "low_income_not_in_work"


def test_stable_work_boundary(policy):
    assert label(policy, months_employed_last_24=12).rule_id == "low_income_stable_work"
    result = label(policy, months_employed_last_24=11)
    assert (result.outcome, result.rule_id) == (Outcome.NEEDS_HUMAN_REVIEW, "unstable_work_history")


# --- order, explanation, version -------------------------------------------------------------


def test_first_match_wins(policy):
    # Low income would approve, but high net wealth comes first.
    result = label(policy, total_assets_aed=Decimal("900000.00"))
    assert (result.outcome, result.rule_id) == (Outcome.SOFT_DECLINE, "high_net_wealth")


def test_label_result_explains_the_decision(policy):
    result = label(
        policy, total_assets_aed=Decimal("600000.00"), total_liabilities_aed=Decimal("0")
    )
    assert result.compared == {"net_wealth_aed": Decimal("600000.00")}
    assert "600000.00" in result.reason
    assert result.policy_version_id == policy.version_id


def test_default_rule_explains_with_its_reason_factors(policy):
    result = label(policy, months_employed_last_24=5)
    assert result.compared == {"months_employed_last_24": 5}
    assert "5 of the last 24 months" in result.reason


def test_version_id_format_and_stability(policy):
    assert re.fullmatch(r"eligibility/v1\+[0-9a-f]{8}", policy.version_id)
    assert load_policy().version_id == policy.version_id


def test_version_id_ignores_line_endings(tmp_path):
    text = POLICY_FILE.read_text(encoding="utf-8").replace("\r\n", "\n")
    lf, crlf = tmp_path / "lf.toml", tmp_path / "crlf.toml"
    lf.write_bytes(text.encode("utf-8"))
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert load_policy(path=lf).version_id == load_policy(path=crlf).version_id
    edited = tmp_path / "edited.toml"
    edited.write_bytes((text + "\n# a comment\n").encode("utf-8"))
    assert load_policy(path=edited).version_id != load_policy(path=lf).version_id


# --- invalid files ---------------------------------------------------------------------------

HEADER = 'name = "eligibility"\nversion = "v9"\n'
DEFAULT_RULE = (
    '[[rules]]\nid = "fallback"\noutcome = "NEEDS_HUMAN_REVIEW"\nreason = "x"\nconditions = []\n'
)


def rule(id="r1", outcome="APPROVE", factor="credit_score", op="ge", value="500", reason="ok"):
    return (
        f'[[rules]]\nid = "{id}"\noutcome = "{outcome}"\nreason = "{reason}"\n'
        f'conditions = [{{ factor = "{factor}", op = "{op}", value = {value} }}]\n'
    )


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("", "policy has no rules"),
        (rule("a") + rule("a") + DEFAULT_RULE, "duplicate rule id a"),
        (rule(outcome="HARD_DECLINE") + DEFAULT_RULE, "unknown outcome HARD_DECLINE in rule r1"),
        (rule(factor="nationality") + DEFAULT_RULE, "unknown factor nationality in rule r1"),
        (rule(op="approx") + DEFAULT_RULE, "unknown operator approx in rule r1"),
        (rule(), "the last rule must be the default (no conditions)"),
        (DEFAULT_RULE + rule(), "the last rule must be the default (no conditions)"),
        (rule(reason="{gender}") + DEFAULT_RULE, "unknown placeholder {gender} in rule r1"),
    ],
    ids=[
        "no-rules",
        "duplicate-id",
        "unknown-outcome",
        "unknown-factor",
        "unknown-operator",
        "missing-default",
        "default-not-last",
        "unknown-placeholder",
    ],
)
def test_invalid_policy_files_are_rejected(tmp_path, body, message):
    path = tmp_path / "bad.toml"
    path.write_text(HEADER + body, encoding="utf-8")
    with pytest.raises(PolicyError, match=re.escape(message)):
        load_policy(path=path)
