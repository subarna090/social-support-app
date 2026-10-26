"""Structured logging and per-application processing traces (FR-016, Principle VII).

Logs only ever contain the whitelisted keys below. Emirates IDs, names and income values are
never logged (Principle I).
"""

import json
import logging
import sys
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
    "run_id",  # synthetic generator (feature 002): run and pack identifiers, never personal data
    "pack_id",
    "document_type",  # feature 004: document types, check ids and model metadata, never values
    "check_id",
    "model",
    "is_fallback",
    "latency_ms",
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


class _CurrentStderrHandler(logging.StreamHandler):
    """Writes to whatever ``sys.stderr`` is at emit time, so a handler created once keeps
    working when stderr is swapped (test capture, or a CLI invoked repeatedly in one process)."""

    def __init__(self) -> None:
        super().__init__(sys.stderr)

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, _value) -> None:
        pass


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a JSON handler to the application logger (idempotent)."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = _CurrentStderrHandler()
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
