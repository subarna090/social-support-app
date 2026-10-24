"""Application use cases: submit (US1), lookup (US2) and review queue (US3)."""

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from social_support.domain.assessor import FALLBACK_RULE_VERSION, Assessor
from social_support.domain.models import (
    ApplicationInput,
    AssessmentResult,
    EmploymentStatus,
    Outcome,
    TraceStatus,
    TraceStep,
)
from social_support.domain.validation import normalise_emirates_id
from social_support.persistence.orm import ApplicationRow, DecisionRow, ProcessingTraceStepRow
from social_support.persistence.repository import ApplicationRepository
from social_support.services.reference import generate_reference
from social_support.services.tracing import LOGGER_NAME, TraceRecord, TraceRecorder

logger = logging.getLogger(f"{LOGGER_NAME}.applications")

MAX_REFERENCE_ATTEMPTS = 5
FALLBACK_FLAG_REASON = "automatic assessment unavailable"
FALLBACK_EXPLANATION = (
    "Automatic assessment was unavailable, so a caseworker will review this application."
    f" Rule: {FALLBACK_RULE_VERSION.id}."
)


@dataclass(frozen=True)
class Submission:
    """A validated submission. ``emirates_id`` is already normalised."""

    full_name: str
    emirates_id: str
    family_size: int
    net_monthly_income_aed: Decimal
    employment_status: EmploymentStatus


@dataclass(frozen=True)
class SubmissionResult:
    reference_number: str
    submitted_at: datetime
    previous_application_exists: bool
    assessment: AssessmentResult
    decided_at: datetime


@dataclass(frozen=True)
class LookupResult:
    submission: Submission
    result: SubmissionResult


@dataclass(frozen=True)
class ReviewItem:
    reference_number: str
    full_name: str
    submitted_at: datetime
    flag_reason: str | None


def _trace_row(record: TraceRecord) -> ProcessingTraceStepRow:
    return ProcessingTraceStepRow(
        sequence=record.sequence,
        step=record.step.value,
        status=record.status.value,
        detail=record.detail,
        occurred_at=record.occurred_at,
    )


class ApplicationService:
    def __init__(self, repository: ApplicationRepository, assessor: Assessor) -> None:
        self.repository = repository
        self.assessor = assessor

    def submit(self, submission: Submission) -> SubmissionResult:
        trace = TraceRecorder()
        submitted_at = datetime.now(UTC)
        trace.record(TraceStep.RECEIVED)
        trace.record(TraceStep.VALIDATED)  # validated by the API schema before reaching here

        reference = generate_reference()
        previous_exists = self.repository.emirates_id_has_applications(submission.emirates_id)
        assessment = self._assess(submission, trace, reference)
        decided_at = datetime.now(UTC)

        for attempt in range(1, MAX_REFERENCE_ATTEMPTS + 1):
            application = self._application_row(
                submission, reference, previous_exists, submitted_at
            )
            decision = self._decision_row(assessment, decided_at)
            trace.record(TraceStep.STORED)
            try:
                self.repository.add_submission(
                    application, decision, [_trace_row(s) for s in trace.steps]
                )
                break
            except IntegrityError:
                self.repository.session.rollback()
                trace.steps.pop()  # discard the failed STORED step
                if attempt == MAX_REFERENCE_ATTEMPTS:
                    raise
                reference = generate_reference()

        returned = trace.record(TraceStep.RESULT_RETURNED)
        self.repository.add_trace_step(application.id, _trace_row(returned))
        logger.info(
            "application assessed",
            extra={
                "reference_number": reference,
                "outcome": assessment.outcome.value,
                "rule_version": assessment.rule_version_id,
            },
        )
        return SubmissionResult(reference, submitted_at, previous_exists, assessment, decided_at)

    def lookup(self, reference_number: str, emirates_id: str) -> LookupResult | None:
        """Return the application only if the reference exists AND the Emirates ID matches.

        Both failure cases return None, so callers can't tell them apart (FR-011).
        """
        reference = reference_number.strip().upper()
        row = self.repository.get_by_reference(reference)
        given_id = normalise_emirates_id(emirates_id) or ""
        stored_id = row.emirates_id if row else ""
        matches = secrets.compare_digest(given_id.encode(), stored_id.encode())
        if row is None or not given_id or not matches:
            logger.info("application lookup", extra={"status": "not_found"})
            return None

        logger.info("application lookup", extra={"reference_number": reference, "status": "found"})
        decision = row.decision
        return LookupResult(
            submission=Submission(
                full_name=row.full_name,
                emirates_id=row.emirates_id,
                family_size=row.family_size,
                net_monthly_income_aed=row.net_monthly_income_aed,
                employment_status=EmploymentStatus(row.employment_status),
            ),
            result=SubmissionResult(
                reference_number=row.reference_number,
                submitted_at=row.submitted_at,
                previous_application_exists=row.previous_application_exists,
                assessment=AssessmentResult(
                    outcome=Outcome(decision.outcome),
                    income_per_member_aed=decision.income_per_member_aed,
                    explanation=decision.explanation,
                    suggested_next_steps=tuple(decision.suggested_next_steps),
                    flag_reason=decision.flag_reason,
                    rule_version_id=decision.rule_version_id,
                ),
                decided_at=decision.decided_at,
            ),
        )

    def review_queue(self) -> list[ReviewItem]:
        """Applications awaiting a caseworker, newest first (FR-012)."""
        return [
            ReviewItem(a.reference_number, a.full_name, a.submitted_at, d.flag_reason)
            for a, d in self.repository.list_needs_review()
        ]

    def _assess(
        self, submission: Submission, trace: TraceRecorder, reference: str
    ) -> AssessmentResult:
        try:
            result = self.assessor.assess(
                ApplicationInput(
                    family_size=submission.family_size,
                    net_monthly_income_aed=submission.net_monthly_income_aed,
                    employment_status=submission.employment_status,
                )
            )
        except Exception as exc:  # any failure routes to a human (FR-015, Principle III)
            trace.record(TraceStep.ASSESSED, TraceStatus.FAILED, type(exc).__name__)
            logger.warning(
                "automatic assessment failed; routed to human review",
                extra={"reference_number": reference, "error_type": type(exc).__name__},
            )
            return AssessmentResult(
                outcome=Outcome.NEEDS_HUMAN_REVIEW,
                income_per_member_aed=None,
                explanation=FALLBACK_EXPLANATION,
                suggested_next_steps=(),
                flag_reason=FALLBACK_FLAG_REASON,
                rule_version_id=FALLBACK_RULE_VERSION.id,
            )
        trace.record(TraceStep.ASSESSED)
        return result

    @staticmethod
    def _application_row(
        submission: Submission, reference: str, previous_exists: bool, submitted_at: datetime
    ) -> ApplicationRow:
        return ApplicationRow(
            reference_number=reference,
            full_name=submission.full_name,
            emirates_id=submission.emirates_id,
            family_size=submission.family_size,
            net_monthly_income_aed=submission.net_monthly_income_aed,
            employment_status=submission.employment_status.value,
            previous_application_exists=previous_exists,
            submitted_at=submitted_at,
        )

    @staticmethod
    def _decision_row(assessment: AssessmentResult, decided_at: datetime) -> DecisionRow:
        return DecisionRow(
            outcome=assessment.outcome.value,
            income_per_member_aed=assessment.income_per_member_aed,
            explanation=assessment.explanation,
            suggested_next_steps=list(assessment.suggested_next_steps),
            flag_reason=assessment.flag_reason,
            rule_version_id=assessment.rule_version_id,
            decided_at=decided_at,
        )
