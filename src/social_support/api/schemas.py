"""Request and response models for API v1 (contracts/api.md)."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from social_support.domain.models import AssessmentResult, EmploymentStatus
from social_support.domain.validation import (
    normalise_emirates_id,
    validate_emirates_id,
    validate_family_size,
    validate_full_name,
    validate_income,
)


def _raise_first(errors) -> None:
    if errors:
        raise ValueError(errors[0].message)


def iso_utc(value: datetime) -> str:
    """ISO 8601 in UTC with a ``Z`` suffix. SQLite drops tzinfo, so naive means UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def money(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}"


class SubmitApplicationRequest(BaseModel):
    # Unknown fields (e.g. nationality) are rejected: no protected attributes (FR-014).
    model_config = ConfigDict(extra="forbid")

    full_name: str
    emirates_id: str
    family_size: int
    net_monthly_income_aed: Decimal
    employment_status: EmploymentStatus

    @field_validator("full_name")
    @classmethod
    def _full_name(cls, value: str) -> str:
        _raise_first(validate_full_name(value))
        return value.strip()

    @field_validator("emirates_id")
    @classmethod
    def _emirates_id(cls, value: str) -> str:
        _raise_first(validate_emirates_id(value))
        return normalise_emirates_id(value)

    @field_validator("family_size")
    @classmethod
    def _family_size(cls, value: int) -> int:
        _raise_first(validate_family_size(value))
        return value

    @field_validator("net_monthly_income_aed")
    @classmethod
    def _income(cls, value: Decimal) -> Decimal:
        _raise_first(validate_income(value))
        return value


class DecisionOut(BaseModel):
    outcome: str
    income_per_member_aed: str | None
    explanation: str
    suggested_next_steps: list[str]
    flag_reason: str | None
    rule_version: str
    decided_at: str

    @classmethod
    def from_assessment(cls, result: AssessmentResult, decided_at: datetime) -> "DecisionOut":
        return cls(
            outcome=result.outcome.value,
            income_per_member_aed=money(result.income_per_member_aed),
            explanation=result.explanation,
            suggested_next_steps=list(result.suggested_next_steps),
            flag_reason=result.flag_reason,
            rule_version=result.rule_version_id,
            decided_at=iso_utc(decided_at),
        )


class SubmitApplicationResponse(BaseModel):
    reference_number: str
    submitted_at: str
    previous_application_exists: bool
    decision: DecisionOut


class LookupRequest(BaseModel):
    # Emirates ID is checked by the service, so any mismatch (including a malformed value)
    # gets the same 404 as an unknown reference.
    model_config = ConfigDict(extra="forbid")

    reference_number: str
    emirates_id: str


class ApplicationOut(BaseModel):
    full_name: str
    emirates_id: str
    family_size: int
    net_monthly_income_aed: str
    employment_status: str


class LookupResponse(SubmitApplicationResponse):
    application: ApplicationOut


class ReviewQueueItem(BaseModel):
    reference_number: str
    full_name: str
    submitted_at: str
    flag_reason: str | None


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
