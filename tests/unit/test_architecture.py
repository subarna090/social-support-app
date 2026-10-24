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
