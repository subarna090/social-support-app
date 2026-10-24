"""Structured logging and per-application processing traces (FR-016, Principle VII).

Logs only ever contain the whitelisted keys below. Emirates IDs, names and income values are
never logged (Principle I).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from social_support.domain.models import TraceStatus, TraceStep

LOGGER_NAME = "social_support"
ALLOWED_EXTRA_KEYS = (
    "reference_number",
    "step",
    "status",
    "outcome",
    "rule_version",
    "error_type",
    "path",
    "fields",  # names of fields that failed validation, never their values
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ALLOWED_EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info and record.exc_info[0] is not None:
            # Exception type only: messages and tracebacks may contain applicant data.
            payload.setdefault("error_type", record.exc_info[0].__name__)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a JSON handler to the application logger (idempotent)."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)


@dataclass(frozen=True)
class TraceRecord:
    sequence: int
    step: TraceStep
    status: TraceStatus
    detail: str | None
    occurred_at: datetime


@dataclass
class TraceRecorder:
    """Collects the ordered processing steps for one application."""

    steps: list[TraceRecord] = field(default_factory=list)

    def record(
        self, step: TraceStep, status: TraceStatus = TraceStatus.OK, detail: str | None = None
    ) -> TraceRecord:
        entry = TraceRecord(len(self.steps) + 1, step, status, detail, datetime.now(UTC))
        self.steps.append(entry)
        return entry
