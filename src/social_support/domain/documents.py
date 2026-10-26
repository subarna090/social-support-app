"""Documents, cross-checks and findings (feature 004, data-model.md). Pure types only."""

from dataclasses import dataclass, field
from enum import StrEnum

from social_support.domain.models import AssessmentResult, Outcome

FORM_LABEL = "Application form"


class DocumentType(StrEnum):
    BANK_STATEMENT = "BANK_STATEMENT"
    EMIRATES_ID_CARD = "EMIRATES_ID_CARD"
    RESUME = "RESUME"
    ASSETS_LIABILITIES = "ASSETS_LIABILITIES"
    CREDIT_REPORT = "CREDIT_REPORT"

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def field_name(self) -> str:
        """The multipart upload field for this document."""
        return _FIELD_NAMES[self]


_LABELS = {
    DocumentType.BANK_STATEMENT: "Bank statement",
    DocumentType.EMIRATES_ID_CARD: "Emirates ID card",
    DocumentType.RESUME: "Resume",
    DocumentType.ASSETS_LIABILITIES: "Assets and liabilities",
    DocumentType.CREDIT_REPORT: "Credit report",
}
_FIELD_NAMES = {
    DocumentType.BANK_STATEMENT: "bank_statement",
    DocumentType.EMIRATES_ID_CARD: "emirates_id_card",
    DocumentType.RESUME: "resume",
    DocumentType.ASSETS_LIABILITIES: "assets_liabilities",
    DocumentType.CREDIT_REPORT: "credit_report",
}

# A document is only usable when every one of these fields was extracted.
REQUIRED_FIELDS: dict[DocumentType, tuple[str, ...]] = {
    DocumentType.BANK_STATEMENT: ("account_holder", "monthly_income_aed"),
    DocumentType.EMIRATES_ID_CARD: ("full_name", "emirates_id", "date_of_birth"),
    DocumentType.RESUME: ("months_employed_last_24",),
    DocumentType.ASSETS_LIABILITIES: ("total_assets_aed", "total_liabilities_aed"),
    DocumentType.CREDIT_REPORT: ("credit_score", "active_credit_defaults", "report_date"),
}


@dataclass(frozen=True)
class ExtractedDocument:
    document_type: DocumentType
    ok: bool
    fields: dict[str, str] = field(default_factory=dict)  # canonical strings: money 2 dp, ISO dates
    items: dict[str, tuple[str, ...]] = field(default_factory=dict)  # list-valued fields
    confidence: dict[str, float] = field(default_factory=dict)  # OCR score per field (ID card)
    error: str | None = None  # human-readable, never file content
    duration_ms: int = 0

    @property
    def missing_fields(self) -> tuple[str, ...]:
        return tuple(f for f in REQUIRED_FIELDS[self.document_type] if not self.fields.get(f))


@dataclass(frozen=True)
class CrossCheckResult:
    check_id: str
    passed: bool | None  # None: skipped because a document it needs could not be read
    form_value: str
    document_value: str
    sources: tuple[DocumentType, ...]
    message: str


@dataclass(frozen=True)
class Finding:
    rule_id: str
    outcome: Outcome  # the outcome this finding implies on its own
    text: str
    sources: tuple[str, ...]  # labels of the documents the values came from


@dataclass(frozen=True)
class CaseAssessment:
    result: AssessmentResult
    findings: tuple[Finding, ...]
