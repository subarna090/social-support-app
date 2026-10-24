"""T045: architecture guards for the layering in plan.md and research R1/R2.

Imports are read with ``ast`` (static), so the checks don't depend on what happens to be loaded.
"""

import ast
import dataclasses
from pathlib import Path

import pytest

from social_support.domain.models import ApplicationInput

SRC = Path(__file__).resolve().parents[2] / "src" / "social_support"


def _imports(package: str) -> dict[str, set[str]]:
    """Map each module file in ``package`` to the absolute module names it imports."""
    found = {}
    files = sorted((SRC / package).rglob("*.py"))
    assert files, f"no modules found in {package}"  # guard against passing vacuously
    for path in files:
        names = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module)
        found[path.relative_to(SRC).as_posix()] = names
    return found


def _violations(package: str, forbidden: tuple[str, ...]) -> list[str]:
    return [
        f"{module} imports {name}"
        for module, names in _imports(package).items()
        for name in sorted(names)
        if any(name == f or name.startswith(f + ".") for f in forbidden)
    ]


def test_ui_talks_to_the_api_only():
    forbidden = tuple(
        f"social_support.{p}"
        for p in ("domain", "assessment", "persistence", "services", "api", "config")
    )
    assert _violations("ui", forbidden) == []


def test_domain_has_no_framework_or_storage_imports():
    assert _violations("domain", ("sqlalchemy", "fastapi", "streamlit", "httpx")) == []


def test_api_does_not_touch_orm_models_directly():
    # Routes go through services; persistence wiring (db, repository) is allowed.
    assert _violations("api", ("social_support.persistence.orm", "sqlalchemy.orm.query")) == []


@pytest.mark.parametrize("package", ["domain", "assessment"])
def test_decision_logic_does_not_depend_on_outer_layers(package):
    forbidden = tuple(f"social_support.{p}" for p in ("persistence", "services", "api", "ui"))
    assert _violations(package, forbidden) == []


def test_assessors_cannot_see_identity():
    fields = {f.name for f in dataclasses.fields(ApplicationInput)}
    assert fields == {"family_size", "net_monthly_income_aed", "employment_status"}


# --- feature 002: labelling and synthetic (research R1) ---------------------------------------

THIRD_PARTY = (
    "faker",
    "reportlab",
    "PIL",
    "openpyxl",
    "pandas",
    "httpx",
    "sqlalchemy",
    "fastapi",
    "streamlit",
)


def test_labelling_is_pure():
    # Feature 005 reuses the policy, so it must not drag in renderers, storage or web frameworks.
    inner = tuple(
        f"social_support.{p}"
        for p in ("persistence", "services", "api", "ui", "assessment", "synthetic", "config")
    )
    assert _violations("labelling", THIRD_PARTY + inner) == []


def test_synthetic_reaches_the_app_only_over_http():
    forbidden = (
        "social_support.api",
        "social_support.persistence",
        "social_support.assessment",
        "social_support.services.applications",
    )
    assert _violations("synthetic", forbidden) == []


@pytest.mark.parametrize("package", ["api", "ui"])
def test_app_does_not_depend_on_the_generator(package):  # FR-021: no new screen or endpoint
    assert _violations(package, ("social_support.synthetic",)) == []


def test_labelling_facts_exclude_identity_and_protected_attributes():
    from social_support.labelling import HouseholdFacts

    names = {f.name for f in dataclasses.fields(HouseholdFacts)}
    assert names == {
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
    }
    protected = {"nationality", "gender", "religion", "ethnicity", "marital_status"}
    assert not names & (protected | {"full_name", "emirates_id"})
