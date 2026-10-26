"""Application use cases: submit (US1), lookup (US2) and review queue (US3), plus feature 004:
submit with documents."""

import dataclasses
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from social_support.assessment.document_rules import FACTOR_SOURCES, DocumentRuleAssessor
from social_support.domain.assessor import FALLBACK_RULE_VERSION, Assessor
from social_support.domain.crosschecks import run_crosschecks
from social_support.domain.documents import (
    FORM_LABEL,
    CaseAssessment,
    CrossCheckResult,
    DocumentType,
    ExtractedDocument,
    Finding,
)
from social_support.domain.enablement import (
    FALLBACK_PLAN,
    EnablementAdvisor,
    EnablementPlan,
    EnablementProfile,
    income_band,
)
from social_support.domain.models import (
    ApplicationInput,
    AssessmentResult,
    EmploymentStatus,
    Outcome,
    TraceStatus,
    TraceStep,
)
from social_support.domain.validation import normalise_emirates_id
from social_support.extraction import extract_all
from social_support.labelling import HouseholdFacts
from social_support.persistence.orm import (
    ApplicationRow,
    CrossCheckRow,
    DecisionInputsRow,
    DecisionRow,
    DocumentRow,
    EnablementPlanRow,
    FindingRow,
    ProcessingTraceStepRow,
)
from social_support.persistence.repository import ApplicationRepository
from social_support.services.reference import generate_reference
from social_support.services.tracing import LOGGER_NAME, TraceRecord, TraceRecorder
from social_support.services.uploads import Upload, store_files, stored_path

logger = logging.getLogger(f"{LOGGER_NAME}.applications")

MAX_REFERENCE_ATTEMPTS = 5
TRACE_DETAIL_MAX = 200  # processing_trace_steps.detail column
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
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class DocumentSubmissionResult:
    """Feature 004: the decision plus what was read from each document and checked."""

    result: SubmissionResult
    documents: dict[DocumentType, ExtractedDocument]
    cross_checks: list[CrossCheckResult]


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
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnablementResult:
    plan: EnablementPlan
    created_at: datetime


@dataclass(frozen=True)
class DocumentSettings:
    """Feature 004 settings the document use cases need (from ``config.Settings``)."""

    upload_dir: Path
    income_tolerance_pct: Decimal = Decimal("10")
    ocr_min_confidence: float = 0.80


@dataclass
class _Extras:
    """Feature 004 rows stored with a decision. Built fresh for every storage attempt."""

    documents: list[DocumentRow] = field(default_factory=list)
    cross_checks: list[CrossCheckRow] = field(default_factory=list)
    inputs: DecisionInputsRow | None = None
    findings: list[FindingRow] = field(default_factory=list)


def _trace_row(record: TraceRecord) -> ProcessingTraceStepRow:
    return ProcessingTraceStepRow(
        sequence=record.sequence,
        step=record.step.value,
        status=record.status.value,
        detail=record.detail,
        occurred_at=record.occurred_at,
    )


def _jsonable(value):
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, Enum):
        return value.value
    return value


def facts_json(facts: HouseholdFacts) -> dict:
    return {f.name: _jsonable(getattr(facts, f.name)) for f in dataclasses.fields(facts)}


def build_facts(
    submission: Submission, documents: dict[DocumentType, ExtractedDocument]
) -> HouseholdFacts | None:
    """Eligibility facts from the form (family size, status) and the documents (research R6).

    None when a document the rules need could not be read, or its values are out of range.
    """
    needed = (
        DocumentType.BANK_STATEMENT,
        DocumentType.ASSETS_LIABILITIES,
        DocumentType.CREDIT_REPORT,
        DocumentType.RESUME,
    )
    if not all(documents[t].ok for t in needed):
        return None
    bank = documents[DocumentType.BANK_STATEMENT].fields
    wealth = documents[DocumentType.ASSETS_LIABILITIES].fields
    credit = documents[DocumentType.CREDIT_REPORT].fields
    resume = documents[DocumentType.RESUME].fields
    try:
        return HouseholdFacts.build(
            family_size=submission.family_size,
            net_monthly_income_aed=Decimal(bank["monthly_income_aed"]),
            employment_status=submission.employment_status,
            months_employed_last_24=int(resume["months_employed_last_24"]),
            total_assets_aed=Decimal(wealth["total_assets_aed"]),
            total_liabilities_aed=Decimal(wealth["total_liabilities_aed"]),
            credit_score=int(credit["credit_score"]),
            active_credit_defaults=int(credit["active_credit_defaults"]),
        )
    except ValueError:
        return None


def prebuilt_findings(
    documents: dict[DocumentType, ExtractedDocument], cross_checks: list[CrossCheckResult]
) -> tuple[Finding, ...]:
    """Unreadable documents and failed cross-checks, as review findings (research R6).

    Built here, not in the assessor, because cross-check messages quote names and ID numbers.
    """
    findings = [
        Finding(
            f"document:{doc.document_type.value}",
            Outcome.NEEDS_HUMAN_REVIEW,
            f"The {doc.document_type.label.lower()} could not be read: {doc.error}.",
            (doc.document_type.label,),
        )
        for doc in documents.values()
        if not doc.ok
    ]
    findings += [
        Finding(
            f"crosscheck:{check.check_id}",
            Outcome.NEEDS_HUMAN_REVIEW,
            check.message,
            (FORM_LABEL, *(s.label for s in check.sources)),
        )
        for check in cross_checks
        if check.passed is False
    ]
    return tuple(findings)


def build_enablement_profile(row: ApplicationRow, documents: dict) -> EnablementProfile:
    """The anonymised profile for the LLM (FR-012): no name, ID, employer or exact income."""
    resume = documents.get(DocumentType.RESUME)
    fields = resume.fields if resume is not None and resume.ok else {}
    items = resume.items if resume is not None and resume.ok else {}
    months = fields.get("months_employed_last_24")
    return EnablementProfile(
        skills=tuple(items.get("skills", ())),
        education=fields.get("education", ""),
        years_experience=fields.get("years_experience", ""),
        last_job_title=fields.get("last_job_title", ""),
        employment_status=row.employment_status,
        months_employed_last_24=int(months) if months else None,
        family_size=row.family_size,
        outcome=row.decision.outcome,
        income_band=income_band(row.decision.income_per_member_aed),
    )


def _plan_from_row(row: EnablementPlanRow) -> EnablementPlan:
    return EnablementPlan(
        training=tuple(row.training),
        job_matches=tuple(row.job_matches),
        career_counselling=row.career_counselling,
        is_fallback=row.is_fallback,
        model=row.model,
    )


def _extraction_detail(documents: dict[DocumentType, ExtractedDocument]) -> str:
    parts = [
        f"{d.document_type.value} {'ok' if d.ok else 'failed'} {d.duration_ms}ms"
        for d in documents.values()
    ]
    return "; ".join(parts)[:TRACE_DETAIL_MAX]


class ApplicationService:
    def __init__(
        self,
        repository: ApplicationRepository,
        assessor: Assessor,
        case_assessor: DocumentRuleAssessor | None = None,
        document_settings: DocumentSettings | None = None,
        advisor: EnablementAdvisor | None = None,
    ) -> None:
        self.repository = repository
        self.assessor = assessor
        self.case_assessor = case_assessor
        self.document_settings = document_settings
        self.advisor = advisor

    def submit(self, submission: Submission) -> SubmissionResult:
        trace = TraceRecorder()
        submitted_at = datetime.now(UTC)
        trace.record(TraceStep.RECEIVED)
        trace.record(TraceStep.VALIDATED)  # validated by the API schema before reaching here

        previous_exists = self.repository.emirates_id_has_applications(submission.emirates_id)
        assessment = self._assess(submission, trace)
        decided_at = datetime.now(UTC)
        reference = self._store(
            submission, assessment, trace, previous_exists, submitted_at, decided_at
        )
        self._finish(trace, reference, assessment)
        return SubmissionResult(reference, submitted_at, previous_exists, assessment, decided_at)

    def submit_with_documents(
        self, submission: Submission, uploads: list[Upload]
    ) -> DocumentSubmissionResult:
        """Feature 004: extract, cross-check, decide, then store everything (US1-US3)."""
        if self.case_assessor is None or self.document_settings is None:
            raise RuntimeError("document submissions are not configured")
        settings = self.document_settings
        trace = TraceRecorder()
        submitted_at = datetime.now(UTC)
        trace.record(TraceStep.RECEIVED)
        trace.record(TraceStep.VALIDATED)

        by_type = {u.document_type: u for u in uploads}
        documents = extract_all(
            {t: u.data for t, u in by_type.items()},
            min_confidence=settings.ocr_min_confidence,
            today=submitted_at.date(),
        )
        unread = sum(not d.ok for d in documents.values())
        trace.record(
            TraceStep.EXTRACTED,
            TraceStatus.FAILED if unread else TraceStatus.OK,
            _extraction_detail(documents),
        )
        cross_checks = run_crosschecks(
            full_name=submission.full_name,
            emirates_id=submission.emirates_id,
            declared_income_aed=submission.net_monthly_income_aed,
            documents=documents,
            tolerance_pct=settings.income_tolerance_pct,
        )
        failed_checks = [c.check_id for c in cross_checks if c.passed is False]
        trace.record(
            TraceStep.CROSS_CHECKED,
            TraceStatus.FAILED if failed_checks else TraceStatus.OK,
            ("failed: " + ", ".join(failed_checks)) if failed_checks else "all passed",
        )

        facts = build_facts(submission, documents)
        case = self._assess_case(facts, prebuilt_findings(documents, cross_checks), trace)
        previous_exists = self.repository.emirates_id_has_applications(submission.emirates_id)
        decided_at = datetime.now(UTC)

        def extras(reference: str) -> _Extras:
            return _Extras(
                documents=[
                    self._document_row(by_type[t], documents[t], reference) for t in documents
                ],
                cross_checks=[
                    CrossCheckRow(
                        check_id=c.check_id,
                        passed=c.passed,
                        form_value=c.form_value[:200],
                        document_value=c.document_value[:200],
                        message=c.message,
                    )
                    for c in cross_checks
                ],
                inputs=DecisionInputsRow(
                    facts=facts_json(facts) if facts else None,
                    fact_sources={k: list(v) for k, v in FACTOR_SOURCES.items()},
                ),
                findings=[
                    FindingRow(
                        sequence=i,
                        rule_id=f.rule_id,
                        outcome=f.outcome.value,
                        text=f.text,
                        sources=list(f.sources),
                    )
                    for i, f in enumerate(case.findings, start=1)
                ],
            )

        reference = self._store(
            submission, case.result, trace, previous_exists, submitted_at, decided_at, extras
        )
        try:
            store_files(settings.upload_dir, reference, [by_type[t] for t in documents])
        except OSError as exc:  # the decision stands; the trace records the missing files
            failed = trace.record(TraceStep.STORED, TraceStatus.FAILED, type(exc).__name__)
            self._add_trace(reference, failed)
            logger.warning(
                "documents could not be written",
                extra={"reference_number": reference, "error_type": type(exc).__name__},
            )
        self._finish(trace, reference, case.result)
        result = SubmissionResult(
            reference, submitted_at, previous_exists, case.result, decided_at, case.findings
        )
        return DocumentSubmissionResult(result, documents, cross_checks)

    def lookup(self, reference_number: str, emirates_id: str) -> LookupResult | None:
        """Return the application only if the reference exists AND the Emirates ID matches.

        Both failure cases return None, so callers can't tell them apart (FR-011).
        """
        row = self._authorised_row(reference_number, emirates_id)
        if row is None:
            logger.info("application lookup", extra={"status": "not_found"})
            return None

        logger.info(
            "application lookup",
            extra={"reference_number": row.reference_number, "status": "found"},
        )
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
                findings=self._findings(decision.id),
            ),
        )

    def enablement_for(self, reference_number: str, emirates_id: str) -> EnablementResult | None:
        """US4: the stored plan, or a new one from the advisor (fallback on any failure).

        Same identity check as ``lookup``: None for an unknown reference or a mismatched ID.
        The plan never changes the decision (FR-013).
        """
        row = self._authorised_row(reference_number, emirates_id)
        if row is None:
            logger.info("enablement requested", extra={"status": "not_found"})
            return None
        stored = self.repository.get_enablement_plan(row.id)
        if stored is not None:
            return EnablementResult(_plan_from_row(stored), stored.created_at)

        profile = build_enablement_profile(
            row, {DocumentType(d.document_type): d for d in self.repository.get_documents(row.id)}
        )
        started = time.perf_counter()
        error_type = None
        try:
            if self.advisor is None:
                raise RuntimeError("no enablement advisor is configured")
            plan = self.advisor.advise(profile)
        except Exception as exc:  # the model is optional: never fail the request (FR-013)
            plan, error_type = FALLBACK_PLAN, type(exc).__name__
        latency_ms = int((time.perf_counter() - started) * 1000)
        created_at = datetime.now(UTC)
        self.repository.add_enablement_plan(
            EnablementPlanRow(
                application_id=row.id,
                created_at=created_at,
                model=plan.model,
                is_fallback=plan.is_fallback,
                profile=profile.as_dict(),
                latency_ms=latency_ms,
                error_type=error_type,
                training=list(plan.training),
                job_matches=list(plan.job_matches),
                career_counselling=plan.career_counselling,
            )
        )
        detail = f"fallback {error_type}" if plan.is_fallback else f"{plan.model} {latency_ms}ms"
        step = TraceRecord(
            sequence=len(row.trace_steps) + 1,  # appended after the submission's steps
            step=TraceStep.ENABLEMENT,
            status=TraceStatus.FAILED if plan.is_fallback else TraceStatus.OK,
            detail=detail[:TRACE_DETAIL_MAX],
            occurred_at=created_at,
        )
        self.repository.add_trace_step(row.id, _trace_row(step))
        logger.info(
            "enablement plan created",
            extra={
                "reference_number": row.reference_number,
                "model": plan.model,
                "is_fallback": plan.is_fallback,
                "latency_ms": latency_ms,
                **({"error_type": error_type} if error_type else {}),
            },
        )
        return EnablementResult(plan, created_at)

    def review_queue(self) -> list[ReviewItem]:
        """Applications awaiting a caseworker, newest first (FR-012)."""
        return [
            ReviewItem(
                a.reference_number,
                a.full_name,
                a.submitted_at,
                d.flag_reason,
                tuple(
                    f.text for f in self._findings(d.id) if f.outcome is Outcome.NEEDS_HUMAN_REVIEW
                ),
            )
            for a, d in self.repository.list_needs_review()
        ]

    # --- helpers ---------------------------------------------------------------------------

    def _authorised_row(self, reference_number: str, emirates_id: str) -> ApplicationRow | None:
        reference = reference_number.strip().upper()
        row = self.repository.get_by_reference(reference)
        given_id = normalise_emirates_id(emirates_id) or ""
        stored_id = row.emirates_id if row else ""
        matches = secrets.compare_digest(given_id.encode(), stored_id.encode())
        if row is None or not given_id or not matches:
            return None
        return row

    def _findings(self, decision_id: int) -> tuple[Finding, ...]:
        return tuple(
            Finding(f.rule_id, Outcome(f.outcome), f.text, tuple(f.sources))
            for f in self.repository.get_findings(decision_id)
        )

    def _store(
        self,
        submission: Submission,
        assessment: AssessmentResult,
        trace: TraceRecorder,
        previous_exists: bool,
        submitted_at: datetime,
        decided_at: datetime,
        extras: Callable[[str], _Extras] | None = None,
    ) -> str:
        """Store in one transaction, retrying with a new reference on a collision."""
        reference = generate_reference()
        for attempt in range(1, MAX_REFERENCE_ATTEMPTS + 1):
            application = self._application_row(
                submission, reference, previous_exists, submitted_at
            )
            decision = self._decision_row(assessment, decided_at)
            rows = extras(reference) if extras else _Extras()
            trace.record(TraceStep.STORED)
            try:
                self.repository.add_submission(
                    application,
                    decision,
                    [_trace_row(s) for s in trace.steps],
                    documents=rows.documents,
                    cross_checks=rows.cross_checks,
                    inputs=rows.inputs,
                    findings=rows.findings,
                )
                return reference
            except IntegrityError:
                self.repository.session.rollback()
                trace.steps.pop()  # discard the failed STORED step
                if attempt == MAX_REFERENCE_ATTEMPTS:
                    raise
                reference = generate_reference()
        raise AssertionError("unreachable")

    def _add_trace(self, reference: str, record: TraceRecord) -> None:
        row = self.repository.get_by_reference(reference)
        self.repository.add_trace_step(row.id, _trace_row(record))

    def _finish(self, trace: TraceRecorder, reference: str, assessment: AssessmentResult) -> None:
        self._add_trace(reference, trace.record(TraceStep.RESULT_RETURNED))
        logger.info(
            "application assessed",
            extra={
                "reference_number": reference,
                "outcome": assessment.outcome.value,
                "rule_version": assessment.rule_version_id,
            },
        )

    def _assess(self, submission: Submission, trace: TraceRecorder) -> AssessmentResult:
        try:
            result = self.assessor.assess(
                ApplicationInput(
                    family_size=submission.family_size,
                    net_monthly_income_aed=submission.net_monthly_income_aed,
                    employment_status=submission.employment_status,
                )
            )
        except Exception as exc:  # any failure routes to a human (FR-015, Principle III)
            return self._fallback(trace, exc)
        trace.record(TraceStep.ASSESSED)
        return result

    def _assess_case(
        self, facts: HouseholdFacts | None, findings: tuple[Finding, ...], trace: TraceRecorder
    ) -> CaseAssessment:
        try:
            case = self.case_assessor.assess_case(facts, findings)
        except Exception as exc:  # any failure routes to a human (Principle III)
            return CaseAssessment(self._fallback(trace, exc), findings)
        trace.record(TraceStep.ASSESSED)
        return case

    @staticmethod
    def _fallback(trace: TraceRecorder, exc: Exception) -> AssessmentResult:
        trace.record(TraceStep.ASSESSED, TraceStatus.FAILED, type(exc).__name__)
        logger.warning(
            "automatic assessment failed; routed to human review",
            extra={"error_type": type(exc).__name__},
        )
        return AssessmentResult(
            outcome=Outcome.NEEDS_HUMAN_REVIEW,
            income_per_member_aed=None,
            explanation=FALLBACK_EXPLANATION,
            suggested_next_steps=(),
            flag_reason=FALLBACK_FLAG_REASON,
            rule_version_id=FALLBACK_RULE_VERSION.id,
        )

    @staticmethod
    def _document_row(upload: Upload, doc: ExtractedDocument, reference: str) -> DocumentRow:
        return DocumentRow(
            document_type=doc.document_type.value,
            original_filename=upload.filename[:255],
            stored_path=stored_path(reference, upload),
            sha256=upload.sha256,
            size_bytes=len(upload.data),
            ok=doc.ok,
            error=doc.error[:300] if doc.error else None,
            fields=dict(doc.fields),
            items={k: list(v) for k, v in doc.items.items()},
            confidence=dict(doc.confidence),
            duration_ms=doc.duration_ms,
        )

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
