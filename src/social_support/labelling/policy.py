"""Load and evaluate a labelling policy: an ordered list of named rules, first match wins.

Format and validation rules: specs/002-synthetic-data-generator/contracts/labelling-policy.md.
"""

import hashlib
import string
import tomllib
from dataclasses import dataclass, fields
from decimal import Decimal
from enum import Enum
from importlib import resources
from pathlib import Path

from social_support.domain.models import Outcome
from social_support.labelling.facts import HouseholdFacts

FACTORS = frozenset(f.name for f in fields(HouseholdFacts))
OPERATORS = frozenset({"lt", "le", "gt", "ge", "eq", "in"})


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class Condition:
    factor: str
    op: str
    value: Decimal | str | tuple[str, ...]

    def holds(self, facts: HouseholdFacts) -> bool:
        actual = getattr(facts, self.factor)
        if self.op == "in":
            return _text(actual) in self.value
        if isinstance(self.value, str):
            return self.op == "eq" and _text(actual) == self.value
        actual = Decimal(actual)
        return {
            "lt": actual < self.value,
            "le": actual <= self.value,
            "gt": actual > self.value,
            "ge": actual >= self.value,
            "eq": actual == self.value,
        }[self.op]


@dataclass(frozen=True)
class Rule:
    id: str
    outcome: Outcome
    conditions: tuple[Condition, ...]
    reason: str

    @property
    def reason_factors(self) -> tuple[str, ...]:
        return tuple(name for _, name, _, _ in string.Formatter().parse(self.reason) if name)


@dataclass(frozen=True)
class LabelResult:
    outcome: Outcome
    rule_id: str
    compared: dict[str, object]
    reason: str
    policy_version_id: str


@dataclass(frozen=True)
class LabellingPolicy:
    name: str
    version: str
    version_id: str
    rules: tuple[Rule, ...]

    def evaluate(self, facts: HouseholdFacts) -> LabelResult:
        for rule in self.rules:
            if all(condition.holds(facts) for condition in rule.conditions):
                factors = [c.factor for c in rule.conditions] or list(rule.reason_factors)
                values = {name: getattr(facts, name) for name in rule.reason_factors}
                return LabelResult(
                    outcome=rule.outcome,
                    rule_id=rule.id,
                    compared={name: getattr(facts, name) for name in dict.fromkeys(factors)},
                    reason=rule.reason.format(**{k: _text(v) for k, v in values.items()}),
                    policy_version_id=self.version_id,
                )
        raise PolicyError("no rule matched")  # unreachable: the last rule always matches


def _text(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def load_policy(
    name: str = "eligibility", version: str = "v1", path: Path | None = None
) -> LabellingPolicy:
    if path is None:
        source = resources.files("social_support.labelling") / "policies" / f"{name}_{version}.toml"
        text = source.read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n")
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PolicyError(f"policy is not valid TOML: {exc}") from exc

    rules = tuple(_parse_rule(raw) for raw in data.get("rules", []))
    _validate(rules)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return LabellingPolicy(
        name=data["name"],
        version=data["version"],
        version_id=f"{data['name']}/{data['version']}+{digest}",
        rules=rules,
    )


def _parse_rule(raw: dict) -> Rule:
    rule_id = raw.get("id", "")
    try:
        outcome = Outcome(raw.get("outcome"))
    except ValueError:
        raise PolicyError(f"unknown outcome {raw.get('outcome')} in rule {rule_id}") from None
    conditions = tuple(_parse_condition(c, rule_id) for c in raw.get("conditions", []))
    rule = Rule(id=rule_id, outcome=outcome, conditions=conditions, reason=raw.get("reason", ""))
    for placeholder in rule.reason_factors:
        if placeholder not in FACTORS:
            raise PolicyError(f"unknown placeholder {{{placeholder}}} in rule {rule_id}")
    return rule


def _parse_condition(raw: dict, rule_id: str) -> Condition:
    factor, op, value = raw.get("factor"), raw.get("op"), raw.get("value")
    if factor not in FACTORS:
        raise PolicyError(f"unknown factor {factor} in rule {rule_id}")
    if op not in OPERATORS or (op == "in") != isinstance(value, list):
        raise PolicyError(f"unknown operator {op} in rule {rule_id}")
    if op == "in":
        return Condition(factor, op, tuple(str(v) for v in value))
    if isinstance(value, str):
        return Condition(factor, op, value)
    return Condition(factor, op, Decimal(str(value)))


def _validate(rules: tuple[Rule, ...]) -> None:
    if not rules:
        raise PolicyError("policy has no rules")
    seen: set[str] = set()
    for rule in rules:
        if rule.id in seen:
            raise PolicyError(f"duplicate rule id {rule.id}")
        seen.add(rule.id)
    defaults = [i for i, rule in enumerate(rules) if not rule.conditions]
    if defaults != [len(rules) - 1]:
        raise PolicyError("the last rule must be the default (no conditions)")
