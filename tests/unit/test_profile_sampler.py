"""T012: household profile invariants, to_facts() and natural sampling."""

from datetime import date
from decimal import Decimal

import pytest

from social_support.domain.models import EmploymentStatus
from social_support.synthetic.profile import (
    IncomeSource,
    Job,
    pack_rng,
    sample_profile,
    to_facts,
)

AS_OF = date(2026, 10, 1)
WORKING = {EmploymentStatus.EMPLOYED, EmploymentStatus.SELF_EMPLOYED}


def sample(seed: int, index: int):
    return sample_profile(pack_rng(seed, index), AS_OF, pack_index=index)


@pytest.fixture(scope="module")
def profiles():
    return [sample(3, i) for i in range(1, 501)]


def test_profile_invariants_hold(profiles):
    for p in profiles:
        assert p.family_size == 1 + len(p.members)
        assert p.active_credit_defaults == sum(a.status == "DEFAULT" for a in p.credit_accounts)
        current = [j for j in p.jobs if j.end is None]
        if p.employment_status in WORKING:
            assert len(current) == 1
        else:
            assert current == []
        for source in p.income_sources:
            if source.kind == "SALARY":
                assert source.payer == current[0].employer
        assert 300 <= p.credit_score <= 900
        assert p.emirates_id.split("-")[1] == str(p.date_of_birth.year)


def test_profiles_stay_within_application_limits(profiles):
    for p in profiles:
        assert 1 <= p.family_size <= 19  # 001 accepts up to 20; a family-size mismatch adds 1
        assert to_facts(p, AS_OF).net_monthly_income_aed <= Decimal("1000000")


def test_to_facts_counts_months_in_the_24_months_before_as_of(profiles):
    profile = profiles[0]
    jobs = (
        Job("A (Demo)", "Driver", start=date(2024, 1, 1), end=date(2025, 3, 1)),  # Oct 24–Mar 25: 6
        Job("B (Demo)", "Driver", start=date(2025, 2, 1), end=date(2025, 6, 1)),  # overlap Feb–Mar
        Job("C (Demo)", "Driver", start=date(2026, 7, 1), end=None),  # Jul–Sep 26: 3
    )
    income = (
        IncomeSource("SALARY", Decimal("4000.00"), "C (Demo)"),
        IncomeSource("RENTAL", Decimal("1500.50"), "Tenant"),
    )
    changed = profile.replace(
        employment_status=EmploymentStatus.EMPLOYED, jobs=jobs, income_sources=income
    )
    facts = to_facts(changed, AS_OF)
    # Window is Oct 2024 .. Sep 2026. A: Oct24–Mar25 (6), B adds Apr–Jun25 (3), C: Jul–Sep26 (3).
    assert facts.months_employed_last_24 == 12
    assert facts.net_monthly_income_aed == Decimal("5500.50")
    assert facts.family_size == changed.family_size


def test_same_pack_seed_gives_identical_profile():
    assert sample(42, 7) == sample(42, 7)
    assert sample(42, 7) != sample(42, 8)
    assert sample(42, 7) != sample(43, 7)


def test_spec_edge_cases_are_reachable(profiles):
    sizes = [p.family_size for p in profiles]
    incomes = [to_facts(p, AS_OF).net_monthly_income_aed for p in profiles]
    assert 1 in sizes
    assert max(sizes) >= 10
    assert Decimal("0.00") in incomes
    assert any(
        p.income_sources and all(s.kind != "SALARY" for s in p.income_sources) for p in profiles
    )
    assert {p.employment_status for p in profiles} == set(EmploymentStatus)


def test_constraints_force_income_and_employment():  # T029
    for index in range(1, 60):
        p = sample_profile(
            pack_rng(8, index),
            AS_OF,
            pack_index=index,
            requires_income=True,
            requires_employment=True,
        )
        assert to_facts(p, AS_OF).net_monthly_income_aed > 0
        assert p.employment_status in WORKING


def test_unconstrained_sampling_is_unchanged_by_the_constraint_option():
    assert sample(42, 7) == sample_profile(pack_rng(42, 7), AS_OF, pack_index=7)
