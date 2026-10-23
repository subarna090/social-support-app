"""Data access. Add and get operations only: there is no update or delete (FR-009, R8)."""

from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from social_support.domain.models import RuleVersionInfo
from social_support.persistence.orm import (
    ApplicationRow,
    AssessmentRuleVersionRow,
    DecisionRow,
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
    ) -> None:
        """Store an application, its decision and its trace in one transaction."""
        application.decision = decision
        application.trace_steps.extend(trace_steps)
        self.session.add(application)
        self.session.commit()

    def add_trace_step(self, application_id: int, step: ProcessingTraceStepRow) -> None:
        step.application_id = application_id
        self.session.add(step)
        self.session.commit()

    def emirates_id_has_applications(self, emirates_id: str) -> bool:
        return self.session.scalar(
            select(exists().where(ApplicationRow.emirates_id == emirates_id))
        )

    def reference_exists(self, reference_number: str) -> bool:
        return self.session.scalar(
            select(exists().where(ApplicationRow.reference_number == reference_number))
        )
