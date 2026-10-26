"""T016, T033, T037: the document-based decision (feature 004, research R5, FR-006 to FR-009)."""

from decimal import Decimal

import pytest

from social_support.assessment.document_rules import DocumentRuleAssessor
from social_support.domain.documents import Finding
from social_support.domain.models import EmploymentStatus, Outcome
from social_support.labelling import HouseholdFacts


def facts(**overrides) -> HouseholdFacts:
    """The approve demo applicant: 6000 AED for 5 people, net wealth 30 000, score 720."""
    values = {
        "family_size": 5,
        "net_monthly_income_aed": Decimal("6000.00"),
        "employment_status": EmploymentStatus.EMPLOYED,
        "months_employed_last_24": 20,
        "total_assets_aed": Decimal("43000.00"),
        "total_liabilities_aed": Decimal("13000.00"),
        "credit_score": 720,
        "active_credit_defaults": 0,
    }
    values.update(overrides)
    return HouseholdFacts.build(**values)


@pytest.fixture(scope="module")
def assessor():
    return DocumentRuleAssessor()


def rule_ids(case):
    return [f.rule_id for f in case.findings]


# --- US1: approve -----------------------------------------------------------------------------


def test_approve_lists_one_positive_finding_per_factor(assessor):
    case = assessor.assess_case(facts(), findings=())
    assert case.result.outcome is Outcome.APPROVE
    assert rule_ids(case) == [
        "income_within_band",
        "wealth_within_limit",
        "credit_good_standing",
        "stable_work",
    ]
    assert case.result.income_per_member_aed == Decimal("1200.00")
    assert case.result.rule_version_id == assessor.rule_version.id
    assert case.result.rule_version_id.startswith("decision/v1+")


def test_every_finding_cites_value_threshold_and_source(assessor):
    case = assessor.assess_case(facts(), findings=())
    by_id = {f.rule_id: f for f in case.findings}
    assert "1200.00" in by_id["income_within_band"].text
    assert "2000.00" in by_id["income_within_band"].text
    assert by_id["income_within_band"].sources == ("Bank statement", "Application form")
    assert "30000.00" in by_id["wealth_within_limit"].text
    assert "500000.00" in by_id["wealth_within_limit"].text
    assert by_id["wealth_within_limit"].sources == ("Assets and liabilities",)
    assert (
        "720" in by_id["credit_good_standing"].text and "550" in by_id["credit_good_standing"].text
    )
    assert by_id["credit_good_standing"].sources == ("Credit report",)
    assert "20" in by_id["stable_work"].text and "12" in by_id["stable_work"].text
    assert by_id["stable_work"].sources == ("Resume",)


def test_people_not_in_work_get_a_not_in_work_finding(assessor):
    case = assessor.assess_case(
        facts(employment_status=EmploymentStatus.UNEMPLOYED, months_employed_last_24=0),
        findings=(),
    )
    assert case.result.outcome is Outcome.APPROVE
    assert "not_in_work" in rule_ids(case)
    assert "unstable_work_history" not in rule_ids(case)


# --- US2: soft decline ------------------------------------------------------------------------


def test_soft_decline_lists_every_failing_factor_with_next_steps(assessor):
    case = assessor.assess_case(
        facts(
            family_size=2,
            net_monthly_income_aed=Decimal("18000.00"),
            total_assets_aed=Decimal("950000.00"),
            total_liabilities_aed=Decimal("300000.00"),
        ),
        findings=(),
    )
    assert case.result.outcome is Outcome.SOFT_DECLINE
    assert {"income_above_band", "high_net_wealth"} <= set(rule_ids(case))
    assert "credit_good_standing" in rule_ids(case)  # positive findings are still listed
    assert case.result.suggested_next_steps
    assert case.result.flag_reason is None


# --- US3: human review ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "rule_id"),
    [
        ({"net_monthly_income_aed": Decimal("11250.00")}, "borderline_income"),  # 2250 / member
        ({"net_monthly_income_aed": Decimal("10000.00")}, "borderline_income"),  # 2000 exactly
        ({"net_monthly_income_aed": Decimal("12500.00")}, "borderline_income"),  # 2500 exactly
        ({"active_credit_defaults": 1}, "active_credit_defaults"),
        ({"credit_score": 520}, "poor_credit_score"),
        ({"months_employed_last_24": 8}, "unstable_work_history"),
    ],
)
def test_uncertain_factors_go_to_human_review(assessor, overrides, rule_id):
    case = assessor.assess_case(facts(**overrides), findings=())
    assert case.result.outcome is Outcome.NEEDS_HUMAN_REVIEW
    assert rule_id in rule_ids(case)
    assert case.result.flag_reason


def test_income_just_above_band_is_soft_decline_not_review(assessor):
    case = assessor.assess_case(facts(net_monthly_income_aed=Decimal("12500.05")), findings=())
    assert case.result.outcome is Outcome.SOFT_DECLINE


def test_given_review_finding_overrides_an_approval(assessor):
    mismatch = Finding(
        "crosscheck:income_vs_bank",
        Outcome.NEEDS_HUMAN_REVIEW,
        "Declared income differs from the bank statement.",
        ("Application form", "Bank statement"),
    )
    case = assessor.assess_case(facts(), findings=(mismatch,))
    assert case.result.outcome is Outcome.NEEDS_HUMAN_REVIEW
    assert rule_ids(case)[0] == "crosscheck:income_vs_bank"
    assert case.result.flag_reason == "Declared income differs from the bank statement."


def test_without_facts_the_rules_are_skipped_and_the_case_is_reviewed(assessor):
    unreadable = Finding(
        "document:CREDIT_REPORT",
        Outcome.NEEDS_HUMAN_REVIEW,
        "The credit report could not be read.",
        ("Credit report",),
    )
    case = assessor.assess_case(None, findings=(unreadable,))
    assert case.result.outcome is Outcome.NEEDS_HUMAN_REVIEW
    assert rule_ids(case) == ["document:CREDIT_REPORT"]
    assert case.result.income_per_member_aed is None


def test_review_wins_over_soft_decline_and_lists_all_findings(assessor):
    case = assessor.assess_case(
        facts(total_assets_aed=Decimal("900000.00"), credit_score=500), findings=()
    )
    assert case.result.outcome is Outcome.NEEDS_HUMAN_REVIEW
    assert {"high_net_wealth", "poor_credit_score"} <= set(rule_ids(case))


def test_flag_reason_joins_review_findings_and_fits_the_column(assessor):
    long = tuple(
        Finding(f"crosscheck:c{i}", Outcome.NEEDS_HUMAN_REVIEW, "x" * 80, ("Application form",))
        for i in range(4)
    )
    case = assessor.assess_case(facts(), findings=long)
    assert len(case.result.flag_reason) <= 200
    assert case.result.flag_reason.startswith("x" * 80 + "; ")


def test_findings_are_listed_most_severe_first_keeping_file_order(assessor):
    mismatch = Finding(
        "crosscheck:income_vs_bank",
        Outcome.NEEDS_HUMAN_REVIEW,
        "Declared income differs from the bank statement.",
        ("Application form", "Bank statement"),
    )
    case = assessor.assess_case(
        facts(net_monthly_income_aed=Decimal("9000.00"), family_size=4), findings=(mismatch,)
    )
    assert rule_ids(case) == [
        "crosscheck:income_vs_bank",
        "borderline_income",
        "wealth_within_limit",
        "credit_good_standing",
        "stable_work",
    ]
