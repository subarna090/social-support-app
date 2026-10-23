"""Pure domain types shared by every layer. No I/O and no framework imports."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class Outcome(StrEnum):
    """Possible recommendations. There is deliberately no hard-decline value (FR-008)."""

    APPROVE = "APPROVE"
    SOFT_DECLINE = "SOFT_DECLINE"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class EmploymentStatus(StrEnum):
    EMPLOYED = "EMPLOYED"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    UNEMPLOYED = "UNEMPLOYED"
    STUDENT = "STUDENT"
    RETIRED = "RETIRED"

    @property
    def label(self) -> str:
        return self.value.replace("_", "-").capitalize()


class TraceStep(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    ASSESSED = "ASSESSED"
    STORED = "STORED"
    RESULT_RETURNED = "RESULT_RETURNED"


class TraceStatus(StrEnum):
    OK = "OK"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ApplicationInput:
    """What an assessor is allowed to see. Identity (name, Emirates ID) is excluded on purpose."""

    family_size: int
    net_monthly_income_aed: Decimal
    employment_status: EmploymentStatus


@dataclass(frozen=True)
class RuleVersionInfo:
    id: str
    name: str
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AssessmentResult:
    outcome: Outcome
    income_per_member_aed: Decimal | None
    explanation: str
    suggested_next_steps: tuple[str, ...]
    flag_reason: str | None
    rule_version_id: str

    def __post_init__(self) -> None:
        if not self.explanation.strip():
            raise ValueError("explanation must not be empty")
        if not self.rule_version_id.strip():
            raise ValueError("rule_version_id must not be empty")
        if self.outcome is Outcome.SOFT_DECLINE and not self.suggested_next_steps:
            raise ValueError("SOFT_DECLINE requires at least one suggested next step")
        if self.outcome is Outcome.NEEDS_HUMAN_REVIEW and not self.flag_reason:
            raise ValueError("NEEDS_HUMAN_REVIEW requires a flag_reason")
