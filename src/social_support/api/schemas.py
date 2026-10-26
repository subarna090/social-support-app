"""Request and response models for API v1 (contracts/api.md)."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from social_support.domain.documents import (
    CrossCheckResult,
    DocumentType,
    ExtractedDocument,
    Finding,
)
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


class FindingOut(BaseModel):
    rule_id: str
    outcome: str
    text: str
    sources: list[str]

    @classmethod
    def from_finding(cls, finding: Finding) -> "FindingOut":
        return cls(
            rule_id=finding.rule_id,
            outcome=finding.outcome.value,
            text=finding.text,
            sources=list(finding.sources),
        )


class DecisionOut(BaseModel):
    outcome: str
    income_per_member_aed: str | None
    explanation: str
    suggested_next_steps: list[str]
    flag_reason: str | None
    rule_version: str
    decided_at: str
    findings: list[FindingOut]  # feature 004; empty for the placeholder rule

    @classmethod
    def from_assessment(
        cls, result: AssessmentResult, decided_at: datetime, findings: tuple[Finding, ...] = ()
    ) -> "DecisionOut":
        return cls(
            outcome=result.outcome.value,
            income_per_member_aed=money(result.income_per_member_aed),
            explanation=result.explanation,
            suggested_next_steps=list(result.suggested_next_steps),
            flag_reason=result.flag_reason,
            rule_version=result.rule_version_id,
            decided_at=iso_utc(decided_at),
            findings=[FindingOut.from_finding(f) for f in findings],
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
    reasons: list[str]  # feature 004: the human-review findings


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]


# --- feature 004: submission with documents (specs/004-poc-demo/contracts/api.md) -------------


class SubmitWithDocumentsForm(SubmitApplicationRequest):
    """The multipart form fields. The five file parts arrive in the same form data, so they are
    set aside here; any other unknown field is still rejected (no protected attributes)."""

    @model_validator(mode="before")
    @classmethod
    def _ignore_file_parts(cls, data):
        if isinstance(data, dict):
            uploads = {t.field_name for t in DocumentType}
            return {k: v for k, v in data.items() if k not in uploads}
        return data


class DocumentOut(BaseModel):
    document_type: str
    label: str
    ok: bool
    error: str | None
    fields: dict[str, str]
    items: dict[str, list[str]]

    @classmethod
    def from_document(cls, doc: ExtractedDocument) -> "DocumentOut":
        return cls(
            document_type=doc.document_type.value,
            label=doc.document_type.label,
            ok=doc.ok,
            error=doc.error,
            fields=dict(doc.fields),
            items={k: list(v) for k, v in doc.items.items()},
        )


class CrossCheckOut(BaseModel):
    check_id: str
    passed: bool | None
    form_value: str
    document_value: str
    message: str

    @classmethod
    def from_result(cls, check: CrossCheckResult) -> "CrossCheckOut":
        return cls(
            check_id=check.check_id,
            passed=check.passed,
            form_value=check.form_value,
            document_value=check.document_value,
            message=check.message,
        )


class DocumentSubmissionResponse(SubmitApplicationResponse):
    documents: list[DocumentOut]
    cross_checks: list[CrossCheckOut]


class EnablementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emirates_id: str


class EnablementOut(BaseModel):
    training: list[str]
    job_matches: list[str]
    career_counselling: str
    is_fallback: bool
    model: str
    created_at: str
