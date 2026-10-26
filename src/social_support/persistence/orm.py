"""SQLAlchemy models. Portable between SQLite and PostgreSQL (research R11).

All tables are append-only: nothing in the codebase updates or deletes rows (FR-009).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AssessmentRuleVersionRow(Base):
    __tablename__ = "assessment_rule_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    parameters: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference_number: Mapped[str] = mapped_column(String(14), unique=True)
    full_name: Mapped[str] = mapped_column(String(100))
    emirates_id: Mapped[str] = mapped_column(String(18), index=True)
    family_size: Mapped[int] = mapped_column(Integer)
    net_monthly_income_aed: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    employment_status: Mapped[str] = mapped_column(String(20))
    previous_application_exists: Mapped[bool] = mapped_column(Boolean)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    decision: Mapped["DecisionRow"] = relationship(back_populates="application")
    trace_steps: Mapped[list["ProcessingTraceStepRow"]] = relationship(
        back_populates="application", order_by="ProcessingTraceStepRow.sequence"
    )


class DecisionRow(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), unique=True)
    outcome: Mapped[str] = mapped_column(String(32))
    income_per_member_aed: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    explanation: Mapped[str] = mapped_column(Text)
    suggested_next_steps: Mapped[list] = mapped_column(JSON)
    flag_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rule_version_id: Mapped[str] = mapped_column(ForeignKey("assessment_rule_versions.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    application: Mapped[ApplicationRow] = relationship(back_populates="decision")


class ProcessingTraceStepRow(Base):
    __tablename__ = "processing_trace_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    step: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    application: Mapped[ApplicationRow] = relationship(back_populates="trace_steps")


# --- feature 004: documents, cross-checks, decision inputs and findings, enablement ------------


class DocumentRow(Base):
    __tablename__ = "application_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(32))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    fields: Mapped[dict] = mapped_column(JSON)
    items: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[dict] = mapped_column(JSON)
    duration_ms: Mapped[int] = mapped_column(Integer)


class CrossCheckRow(Base):
    __tablename__ = "cross_check_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    check_id: Mapped[str] = mapped_column(String(64))
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    form_value: Mapped[str] = mapped_column(String(200))
    document_value: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)


class DecisionInputsRow(Base):
    __tablename__ = "decision_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), unique=True)
    facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # None: rules were skipped
    fact_sources: Mapped[dict] = mapped_column(JSON)


class FindingRow(Base):
    __tablename__ = "decision_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    rule_id: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON)


class EnablementPlanRow(Base):
    __tablename__ = "enablement_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model: Mapped[str] = mapped_column(String(64))
    is_fallback: Mapped[bool] = mapped_column(Boolean)
    profile: Mapped[dict] = mapped_column(JSON)  # exactly what was sent to the model
    latency_ms: Mapped[int] = mapped_column(Integer)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    training: Mapped[list] = mapped_column(JSON)
    job_matches: Mapped[list] = mapped_column(JSON)
    career_counselling: Mapped[str] = mapped_column(Text)
