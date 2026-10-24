"""T034: summary.csv for model training (FR-014, US3 scenarios 1-4, contracts/pack-format.md)."""

import csv

import pytest

from social_support.synthetic.run import GenerationRequest, generate
from tests.integration import pack_checks

COLUMNS = [
    "pack_id",
    "family_size",
    "net_monthly_income_aed",
    "income_per_member_aed",
    "employment_status",
    "months_employed_last_24",
    "total_assets_aed",
    "total_liabilities_aed",
    "net_wealth_aed",
    "credit_score",
    "active_credit_defaults",
    "eligibility_outcome",
    "eligibility_rule_id",
    "expected_routing",
    "inconsistency_count",
    "inconsistency_types",
    "audit_nationality",
    "audit_gender",
]
PROTECTED = ("nationality", "gender", "religion", "ethnicity", "marital")


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    request = GenerationRequest(
        count=30,
        seed=12,
        inconsistency_rate_pct=20,
        outcome_mix_pct={"APPROVE": 40, "SOFT_DECLINE": 40, "NEEDS_HUMAN_REVIEW": 20},
        output_root=tmp_path_factory.mktemp("d"),
    )
    return generate(request)


@pytest.fixture(scope="module")
def rows(run):
    with (run.folder / "summary.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def test_columns_and_order(rows):
    names, data = rows
    assert names == COLUMNS
    assert [r["pack_id"] for r in data] == [f"pack-{i:04d}" for i in range(1, 31)]


def test_rows_match_answer_keys(run, rows):
    _, data = rows
    for row in data:
        _, key = pack_checks.load(run.folder / "packs" / row["pack_id"])
        for field, value in key["facts"].items():
            assert row[field] == str(value), (row["pack_id"], field)
        assert row["eligibility_outcome"] == key["eligibility"]["outcome"]
        assert row["eligibility_rule_id"] == key["eligibility"]["rule_id"]
        assert row["expected_routing"] == key["expected_routing"]
        record = key["inconsistency"]
        assert row["inconsistency_count"] == ("1" if record else "0")
        assert row["inconsistency_types"] == (record["type"] if record else "")
        assert row["audit_nationality"] == key["profile"]["nationality"]
        assert row["audit_gender"] == key["profile"]["gender"]


def test_outcome_mix_is_met(run, rows):  # US3 scenario 2
    _, data = rows
    counts = {
        o: sum(r["eligibility_outcome"] == o for r in data)
        for o in ("APPROVE", "SOFT_DECLINE", "NEEDS_HUMAN_REVIEW")
    }
    assert counts == {"APPROVE": 12, "SOFT_DECLINE": 12, "NEEDS_HUMAN_REVIEW": 6}
    assert run.counts["eligibility"] == counts
    assert sum(r["inconsistency_count"] == "1" for r in data) == 6


def test_protected_attributes_only_in_audit_columns(rows):  # US3 scenario 4
    names, _ = rows
    for name in names:
        if any(word in name for word in PROTECTED):
            assert name.startswith("audit_"), name
