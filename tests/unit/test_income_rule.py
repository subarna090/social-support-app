"""T020: placeholder assessment rule v0.1 (data-model.md, FR-005 to FR-008, FR-013)."""

import re
from decimal import Decimal

import pytest

from social_support.assessment.income_rule import IncomePerMemberRuleAssessor
from social_support.domain.models import ApplicationInput, EmploymentStatus, Outcome


def assess(family: int, income: str, status=EmploymentStatus.EMPLOYED, **params):
    assessor = IncomePerMemberRuleAssessor(**params)
    return assessor.assess(ApplicationInput(family, Decimal(income), status))


@pytest.mark.parametrize(
    ("income", "expected"),
    [
        ("1999.99", Outcome.APPROVE),
        ("2000.00", Outcome.NEEDS_HUMAN_REVIEW),
        ("2500.00", Outcome.NEEDS_HUMAN_REVIEW),
        ("2500.01", Outcome.SOFT_DECLINE),
        ("0", Outcome.APPROVE),
    ],
)
def test_outcome_at_boundaries(income, expected):
    assert assess(1, income).outcome is expected


def test_borderline_has_flag_reason_and_mentions_caseworker():
    result = assess(1, "2250.00")
    assert result.flag_reason == "borderline income"
    assert "caseworker" in result.explanation


def test_soft_decline_has_next_steps():
    result = assess(1, "3000.00")
    assert len(result.suggested_next_steps) >= 1
    assert result.flag_reason is None


def test_approve_has_no_flag_or_next_steps():
    result = assess(4, "6000.00")
    assert result.flag_reason is None
    assert result.suggested_next_steps == ()


def test_income_per_member_rounds_half_up_to_2dp():
    assert assess(3, "1000.00").income_per_member_aed == Decimal("333.33")
    assert assess(8, "1.00").income_per_member_aed == Decimal("0.13")  # 0.125 rounds up


def test_explanation_cites_figures_status_and_rule_version():
    result = assess(4, "6000.00", EmploymentStatus.SELF_EMPLOYED)
    for fragment in ("1500.00", "2000.00", "Self-employed", result.rule_version_id):
        assert fragment in result.explanation


def test_rule_version_format_and_stability():
    a = IncomePerMemberRuleAssessor()
    assert re.fullmatch(r"income-per-member/v0\.1\+[0-9a-f]{8}", a.rule_version.id)
    assert IncomePerMemberRuleAssessor().rule_version.id == a.rule_version.id
    assert assess(4, "6000.00").rule_version_id == a.rule_version.id


def test_rule_version_changes_with_either_parameter():
    base = IncomePerMemberRuleAssessor().rule_version.id
    other_threshold = IncomePerMemberRuleAssessor(threshold_aed=Decimal("1800")).rule_version.id
    other_band = IncomePerMemberRuleAssessor(band_upper_aed=Decimal("2600")).rule_version.id
    assert len({base, other_threshold, other_band}) == 3


def test_rule_parameters_are_recorded():
    info = IncomePerMemberRuleAssessor().rule_version
    assert info.name == "income-per-member"
    assert info.parameters == {"threshold_aed": "2000.00", "band_upper_aed": "2500.00"}
