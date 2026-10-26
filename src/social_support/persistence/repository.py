"""Data access. Add and get operations only: there is no update or delete (FR-009, R8)."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from social_support.domain.models import Outcome, RuleVersionInfo
from social_support.persistence.orm import (
    ApplicationRow,
    AssessmentRuleVersionRow,
    CrossCheckRow,
    DecisionInputsRow,
    DecisionRow,
    DocumentRow,
    EnablementPlanRow,
    FindingRow,
    ProcessingTraceStepRow,
)


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_rule_version(self, info: RuleVersionInfo) -> None:
        """Insert the rule version if it is new. Existing rows are never modified."""
        if self.session.get(AssessmentRuleVersionRow, info.id) is None:
            self.session.add(
                AssessmentRuleVersionRow(
                    id=info.id,
                    name=info.name,
                    parameters=dict(info.parameters),
                    created_at=datetime.now(UTC),
                )
            )
            self.session.commit()

    def add_submission(
        self,
        application: ApplicationRow,
        decision: DecisionRow,
        trace_steps: list[ProcessingTraceStepRow],
        *,
        documents: Sequence[DocumentRow] = (),
        cross_checks: Sequence[CrossCheckRow] = (),
        inputs: DecisionInputsRow | None = None,
        findings: Sequence[FindingRow] = (),
    ) -> None:
        """Store an application, its decision, its trace and (feature 004) its documents,
        cross-checks, decision inputs and findings in one transaction."""
        application.decision = decision
        application.trace_steps.extend(trace_steps)
        self.session.add(application)
        self.session.flush()  # assigns application.id and decision.id
        for row in (*documents, *cross_checks):
            row.application_id = application.id
            self.session.add(row)
        for row in (*([inputs] if inputs else []), *findings):
            row.decision_id = decision.id
            self.session.add(row)
        self.session.commit()

    def add_trace_step(self, application_id: int, step: ProcessingTraceStepRow) -> None:
        step.application_id = application_id
        self.session.add(step)
        self.session.commit()

    def emirates_id_has_applications(self, emirates_id: str) -> bool:
        return self.session.scalar(
            select(exists().where(ApplicationRow.emirates_id == emirates_id))
        )

    def get_by_reference(self, reference_number: str) -> ApplicationRow | None:
        """The application with its decision loaded, or None."""
        return self.session.scalar(
            select(ApplicationRow)
            .options(selectinload(ApplicationRow.decision))
            .where(ApplicationRow.reference_number == reference_number)
        )

    def list_needs_review(self) -> list[tuple[ApplicationRow, DecisionRow]]:
        """Applications whose decision is Needs Human Review, newest first."""
        rows = self.session.execute(
            select(ApplicationRow, DecisionRow)
            .join(DecisionRow, DecisionRow.application_id == ApplicationRow.id)
            .where(DecisionRow.outcome == Outcome.NEEDS_HUMAN_REVIEW.value)
            .order_by(ApplicationRow.submitted_at.desc(), ApplicationRow.id.desc())
        )
        return [(application, decision) for application, decision in rows]

    def reference_exists(self, reference_number: str) -> bool:
        return self.session.scalar(
            select(exists().where(ApplicationRow.reference_number == reference_number))
        )

    # --- feature 004 ---------------------------------------------------------------------------

    def get_documents(self, application_id: int) -> list[DocumentRow]:
        return list(
            self.session.scalars(
                select(DocumentRow)
                .where(DocumentRow.application_id == application_id)
                .order_by(DocumentRow.id)
            )
        )

    def get_cross_checks(self, application_id: int) -> list[CrossCheckRow]:
        return list(
            self.session.scalars(
                select(CrossCheckRow)
                .where(CrossCheckRow.application_id == application_id)
                .order_by(CrossCheckRow.id)
            )
        )

    def get_decision_inputs(self, decision_id: int) -> DecisionInputsRow | None:
        return self.session.scalar(
            select(DecisionInputsRow).where(DecisionInputsRow.decision_id == decision_id)
        )

    def get_findings(self, decision_id: int) -> list[FindingRow]:
        return list(
            self.session.scalars(
                select(FindingRow)
                .where(FindingRow.decision_id == decision_id)
                .order_by(FindingRow.sequence)
            )
        )

    def add_enablement_plan(self, plan: EnablementPlanRow) -> None:
        self.session.add(plan)
        self.session.commit()

    def get_enablement_plan(self, application_id: int) -> EnablementPlanRow | None:
        """The latest plan for the application, or None."""
        return self.session.scalar(
            select(EnablementPlanRow)
            .where(EnablementPlanRow.application_id == application_id)
            .order_by(EnablementPlanRow.id.desc())
            .limit(1)
        )
