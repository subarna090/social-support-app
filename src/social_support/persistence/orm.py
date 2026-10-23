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
