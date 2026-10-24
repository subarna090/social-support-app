"""T026: inconsistency selection, applicability and injection (FR-007-FR-009, FR-011, R8)."""

import random
from collections import Counter
from datetime import date
from decimal import Decimal

import pytest

from social_support.domain.models import EmploymentStatus, Outcome
from social_support.labelling import load_policy
from social_support.synthetic.identities import luhn_check_digit
from social_support.synthetic.inconsistencies import (
    InconsistencyType,
    affected_count,
    applies,
    inject,
    select_slots,
)
from social_support.synthetic.pack import build_pack
from social_support.synthetic.profile import pack_rng, sample_profile

AS_OF = date(2026, 10, 1)
ALL = tuple(InconsistencyType)


def make_pack(index=1, seed=11, **constraints):
    rng = pack_rng(seed, index)
    profile = sample_profile(rng, AS_OF, pack_index=index, **constraints)
    return build_pack(index, profile, load_policy(), AS_OF, rng), rng


# --- selection --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "rate", "expected"), [(100, 30, 30), (5, 50, 3), (10, 0, 0), (7, 100, 7), (3, 50, 2)]
)
def test_affected_count_rounds_half_up(count, rate, expected):
    assert affected_count(count, rate) == expected


def test_select_slots_is_exact_and_uses_requested_types():
    slots = select_slots(random.Random(1), 200, 30, (InconsistencyType.ADDRESS_MISMATCH,))
    assert len(slots) == 60
    assert set(slots.values()) == {InconsistencyType.ADDRESS_MISMATCH}
    assert all(1 <= index <= 200 for index in slots)


def test_select_slots_is_deterministic_and_spreads_types():
    a = select_slots(random.Random(5), 100, 50, ALL)
    assert a == select_slots(random.Random(5), 100, 50, ALL)
    assert set(Counter(a.values())) == set(ALL)


# --- applicability ----------------------------------------------------------------------------


def test_applicability_rules():
    working, _ = make_pack(requires_employment=True)
    assert applies(InconsistencyType.EMPLOYMENT_MISMATCH, working.profile)
    not_working = working.profile.replace(employment_status=EmploymentStatus.UNEMPLOYED, jobs=())
    assert not applies(InconsistencyType.EMPLOYMENT_MISMATCH, not_working)
    no_income = working.profile.replace(income_sources=())
    assert not applies(InconsistencyType.INCOME_MISMATCH, no_income)
    for kind in (
        InconsistencyType.ADDRESS_MISMATCH,
        InconsistencyType.FAMILY_SIZE_MISMATCH,
        InconsistencyType.IDENTITY_MISMATCH,
    ):
        assert applies(kind, no_income)


@pytest.mark.parametrize("index", range(1, 40))
def test_constrained_sampling_makes_the_type_applicable(index):
    pack, _ = make_pack(index=index, requires_income=True, requires_employment=True)
    assert applies(InconsistencyType.INCOME_MISMATCH, pack.profile)
    assert applies(InconsistencyType.EMPLOYMENT_MISMATCH, pack.profile)


# --- injection --------------------------------------------------------------------------------


def _inject(kind, index=1, **constraints):
    pack, rng = make_pack(index=index, **constraints)
    label_before = pack.label
    record = inject(pack, kind, rng)
    assert pack.label == label_before  # FR-011: eligibility unchanged
    assert pack.expected_routing is Outcome.NEEDS_HUMAN_REVIEW
    assert record["type"] == kind.value
    assert record["altered_value"] != record["true_value"]
    assert pack.inconsistency == record
    return pack, record


@pytest.mark.parametrize("index", range(1, 15))
def test_income_mismatch_under_reports_the_form_by_20_to_40_percent(index):
    pack, record = _inject(InconsistencyType.INCOME_MISMATCH, index, requires_income=True)
    true, altered = Decimal(record["true_value"]), Decimal(record["altered_value"])
    assert Decimal("0.60") * true - 1 <= altered <= Decimal("0.80") * true + 1
    assert record["documents"] == ["form", "bank_statement"]
    assert pack.form["net_monthly_income_aed"] == record["altered_value"]
    assert pack.form["submission"]["net_monthly_income_aed"] == record["altered_value"]
    assert pack.views["bank_statement"]["monthly_income_credits_aed"] == record["true_value"]


def test_address_mismatch_changes_only_the_credit_report():
    pack, record = _inject(InconsistencyType.ADDRESS_MISMATCH)
    assert record["documents"] == ["form", "credit_report"]
    assert pack.views["credit_report"]["address"] == record["altered_value"]
    assert pack.views["bank_statement"]["address"] == record["true_value"]


@pytest.mark.parametrize("index", range(1, 20))
def test_family_size_mismatch_changes_the_form_by_one_member(index):
    pack, record = _inject(InconsistencyType.FAMILY_SIZE_MISMATCH, index)
    true, altered = int(record["true_value"]), int(record["altered_value"])
    assert abs(true - altered) == 1 and altered >= 1
    assert pack.form["family_size"] == altered == 1 + len(pack.form["family_members"])
    assert pack.form["submission"]["family_size"] == altered
    assert len(pack.views["credit_report"]["household_members"]) + 1 == true
    assert record["documents"] == ["form", "credit_report"]


@pytest.mark.parametrize("index", range(1, 20))
def test_identity_mismatch_alters_the_id_card(index):
    pack, record = _inject(InconsistencyType.IDENTITY_MISMATCH, index)
    card = pack.views["emirates_id"]
    assert record["documents"] == ["form", "emirates_id"]
    assert record["field"] in {"full_name", "emirates_id"}
    assert card[record["field"]] == record["altered_value"]
    assert pack.form[record["field"]] == record["true_value"]
    if record["field"] == "emirates_id":
        digits = record["altered_value"].replace("-", "")
        assert int(digits[-1]) == luhn_check_digit(digits[:-1])
        assert digits[7:9] == "00"  # still in the reserved block


def test_employment_mismatch_changes_the_resume_employer():
    pack, record = _inject(InconsistencyType.EMPLOYMENT_MISMATCH, requires_employment=True)
    resume = pack.views["resume"]
    assert record["documents"] == ["form", "resume"]
    assert resume["current_employer"] == record["altered_value"]
    current_jobs = [j for j in resume["jobs"] if j["end"] is None]
    assert current_jobs[0]["employer"] == record["altered_value"]
    assert pack.form["employer"] == record["true_value"]


def test_injecting_an_inapplicable_type_is_refused():
    pack, rng = make_pack()
    pack.profile = pack.profile.replace(employment_status=EmploymentStatus.STUDENT, jobs=())
    with pytest.raises(ValueError, match="does not apply"):
        inject(pack, InconsistencyType.EMPLOYMENT_MISMATCH, rng)
