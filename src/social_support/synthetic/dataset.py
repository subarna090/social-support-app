"""``summary.csv``: one row per pack for model training and analysis (FR-014, research R10).

Protected attributes appear only as ``audit_`` columns: for the fairness evaluation that
Constitution IV requires, never as model inputs. Feature 005 drops every ``audit_`` column.
"""

from dataclasses import fields
from pathlib import Path

import pandas as pd

from social_support.labelling import HouseholdFacts
from social_support.synthetic.pack import ApplicantPack, jsonable

FACT_COLUMNS = [f.name for f in fields(HouseholdFacts)]
COLUMNS = (
    ["pack_id"]
    + FACT_COLUMNS
    + [
        "eligibility_outcome",
        "eligibility_rule_id",
        "expected_routing",
        "inconsistency_count",
        "inconsistency_types",
        "audit_nationality",
        "audit_gender",
    ]
)


def summary_row(pack: ApplicantPack) -> dict:
    facts = jsonable(pack.facts)
    record = pack.inconsistency
    return {
        "pack_id": pack.pack_id,
        **{name: facts[name] for name in FACT_COLUMNS},
        "eligibility_outcome": pack.label.outcome.value,
        "eligibility_rule_id": pack.label.rule_id,
        "expected_routing": pack.expected_routing.value,
        "inconsistency_count": 1 if record else 0,
        "inconsistency_types": record["type"] if record else "",
        "audit_nationality": pack.profile.nationality,
        "audit_gender": pack.profile.gender,
    }


def write_summary(folder: Path, rows: list[dict]) -> Path:
    path = folder / "summary.csv"
    frame = pd.DataFrame(rows, columns=COLUMNS).astype(str)
    frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    return path
