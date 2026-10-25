# Data Model: Document Extraction

Feature 003 adds pure domain types for extraction, mutable **draft** tables, and append-only tables
for the documents and extraction of a **submitted** application. Conventions from 001 still hold:

- Money is a `Decimal` internally and a 2-dp string in JSON.
- Timestamps are UTC ISO strings ending in `Z`.
- Submitted-application tables are append-only, and their repository has add and get methods only.

Tables are still created with `create_all` (no migrations yet, per CLAUDE.md). An existing
`data/app.db` from 001 or 002 gains the new tables on the next start. Old applications simply have
no documents.

---

## Domain types (`domain/extraction.py`, pure)

### DocumentType (StrEnum)

`BANK_STATEMENT`, `EMIRATES_ID`, `RESUME`, `ASSETS_LIABILITIES`, `CREDIT_REPORT`. Each has a
display label ("Bank statement", "Emirates ID card", "Resume", "Assets and liabilities",
"Credit report") and an accepted file kind (`pdf`, `image`, `pdf`, `xlsx`, `pdf`). All five are
required for submission (FR-012).

### DocumentStatus (StrEnum)

`WAITING → READING → READ | FAILED`. `READ` means extraction finished, even if some values are
uncertain or not found. `FAILED` means the document as a whole could not be read; its
`failure_reason` says why.

### ExtractedField (frozen dataclass)

| Field | Type | Rule |
|---|---|---|
| `path` | str | catalogue path, for example `bank_statement.income_credits[0].amount_aed` (R7) |
| `kind` | `FieldKind` | `TEXT`, `MONEY`, `DATE`, `MONTH`, `INTEGER`, `ENUM`, `EMIRATES_ID` |
| `value` | str \| None | canonical string form; `None` means **not found** (FR-005) |
| `confidence` | Decimal 0–1 \| None | `None` when not found (R8) |
| `uncertain` | bool | `confidence < threshold`; always false when not found |
| `routing` | bool | from the catalogue (FR-019) |
| `source` | `DocumentType` | the document it came from (FR-003) |

Validation: `value is None` ⇔ `confidence is None`. Money values parse as `Decimal` with 2 dp, and
dates as ISO dates.

### DocumentExtraction (frozen dataclass)

The result of one extraction run over one document.

| Field | Type | Rule |
|---|---|---|
| `document_type` | DocumentType | |
| `status` | `READ` \| `FAILED` | |
| `failure_reason` | str \| None | required when `FAILED`; plain words, no document content |
| `fields` | tuple[ExtractedField, ...] | empty when `FAILED` |
| `warnings` | tuple[str, ...] | for example "1 resume line could not be confirmed in the text" |
| `method_id` | str | for example `bank-statement-parser/1`, `resume-llm/1`, `id-card-ocr/1` |
| `method_versions` | dict[str, str] | for example `{"model": "qwen2.5:7b", "model_digest": "845dbda0…", "rapidocr": "1.4.4"}` |
| `steps` | tuple[ExtractionStep, ...] | timing per internal step (R22): `name`, `duration_ms`, optional token counts |
| `started_at`, `finished_at` | datetime (UTC) | |

Derived properties:
- `problems()`: the failed document, or its uncertain routing fields, as plain sentences. The gate
  and the caseworker view both use it.
- `value(path)`: lookup by path.

### DocumentExtractor (Protocol)

```python
class DocumentExtractor(Protocol):
    document_type: DocumentType
    method_id: str
    def extract(self, content: bytes) -> DocumentExtraction: ...
```

Every implementation:
- must return `FAILED` with a reason, rather than raise, for unreadable input (FR-018)
- must never return a value it cannot find (FR-005, R9)
- must stamp `method_id` and `method_versions` (FR-017)

`build_extractors(settings) -> dict[DocumentType, DocumentExtractor]` constructs the real ones
lazily. Tests inject fakes through `create_app(settings, assessor=None, extractors=None)`.

### CoveredField and FieldComparison (frozen dataclasses)

`CoveredField`: `FULL_NAME`, `EMIRATES_ID`, `FAMILY_SIZE`, `NET_MONTHLY_INCOME`,
`EMPLOYMENT_STATUS` (FR-010, research R15).

`FieldComparison`:

| Field | Type |
|---|---|
| `field` | CoveredField |
| `form_value` | str \| None |
| `document_value` | str \| None (display form) |
| `source` | DocumentType |
| `differs` | bool (false when either side is missing) |
| `document_value_uncertain` | bool |
| `available` | bool (false while the source document is not read, or the value was not found) |

### ExtractionGateResult

`routed: bool` and `problems: tuple[str, ...]`. When `routed` is true, `ApplicationService` stores
an `AssessmentResult(outcome=NEEDS_HUMAN_REVIEW, rule_version_id="extraction-gate/v1", …)`
(research R14).

---

## Draft tables (mutable, `DraftRepository`)

Only the applicant's draft id grants access (FR-015). Rows are deleted on submission (after copying)
or when the draft expires (FR-014).

### `drafts`

| Column | Type | Rule |
|---|---|---|
| `id` | String(64) PK | `secrets.token_urlsafe(32)` |
| `created_at` | DateTime(tz) | |
| `expires_at` | DateTime(tz) | `created_at + DRAFT_TTL_HOURS` (24) |

### `draft_documents`

One row per (draft, document type). Replacing a document overwrites the row and bumps
`generation`.

| Column | Type | Rule |
|---|---|---|
| `id` | Integer PK | |
| `draft_id` | FK → drafts.id, on delete cascade | |
| `document_type` | String(24) | unique with `draft_id` |
| `filename` | String(255) | as uploaded; display only |
| `media_type` | String(80) \| null | detected from the leading bytes (R12) |
| `size_bytes` | Integer | |
| `sha256` | String(64) \| null | null when not stored (oversized) |
| `status` | String(16) | DocumentStatus |
| `failure_reason` | String(200) \| null | |
| `generation` | Integer | starts at 1, +1 on each replacement; stale job results are discarded (R11) |
| `result` | JSON \| null | the serialised `DocumentExtraction` once read or failed |
| `attached_at` | DateTime(tz) | |

### `document_contents`

Shared by drafts and submitted applications; content-addressed.

| Column | Type | Rule |
|---|---|---|
| `sha256` | String(64) PK | |
| `content` | LargeBinary | the original bytes, unchanged (FR-016) |
| `size_bytes` | Integer | |
| `created_at` | DateTime(tz) | |

The expiry job deletes contents that no draft or application document references any more. Rows
referenced by an `application_documents` row are never deleted.

**State transitions** (`draft_documents.status`):

```text
attach / replace ─▶ WAITING ──(worker picks job)──▶ READING ──▶ READ
       ▲                │                              │
       │                └──(type check fails, size)────┴──▶ FAILED
       └────────────────────── replace (generation + 1) ◀────┘
startup recovery: WAITING | READING ─▶ FAILED ("reading was interrupted; replace the document")
remove: row deleted (only before submission)
```

Type and size checks run at upload time, so a wrong-type or oversized file goes straight to
`FAILED` without being queued.

---

## Submitted-application tables (append-only, `ApplicationRepository`)

Written in the same transaction as `applications` and `decisions` (research R13). There are no
update or delete methods (001 FR-009, this spec FR-016).

### `application_documents`

| Column | Type | Rule |
|---|---|---|
| `id` | Integer PK | |
| `application_id` | FK → applications.id, index | |
| `document_type` | String(24) | unique with `application_id` |
| `filename` | String(255) | |
| `media_type` | String(80) \| null | |
| `size_bytes` | Integer | |
| `sha256` | FK → document_contents.sha256 \| null | null only for oversized documents |
| `status` | String(16) | `READ` or `FAILED` (never WAITING or READING; submission refuses those, FR-012) |
| `failure_reason` | String(200) \| null | |
| `attached_at` | DateTime(tz) | |

### `extraction_results`

| Column | Type | Rule |
|---|---|---|
| `id` | Integer PK | |
| `application_document_id` | FK → application_documents.id, unique | |
| `method_id` | String(64) | FR-017 |
| `method_versions` | JSON | |
| `status` | String(16) | READ or FAILED |
| `failure_reason` | String(200) \| null | |
| `warnings` | JSON (list[str]) | |
| `steps` | JSON | timings (R22) |
| `confidence_threshold` | Numeric(4, 2) | the threshold in force, for replay (Constitution IV) |
| `started_at`, `finished_at` | DateTime(tz) | |

### `extracted_fields`

| Column | Type | Rule |
|---|---|---|
| `id` | Integer PK | |
| `extraction_result_id` | FK → extraction_results.id, index | |
| `path` | String(120) | catalogue path |
| `kind` | String(16) | FieldKind |
| `value` | Text \| null | null = not found |
| `confidence` | Numeric(4, 3) \| null | |
| `uncertain` | Boolean | |
| `routing` | Boolean | |

`source` is the parent document's `document_type`, so it is not repeated per row.

### Changes to existing tables

- `applications`: unchanged columns. A new relationship `documents` points to
  `application_documents`.
- `decisions`: unchanged. Extraction-routed decisions use `rule_version_id = "extraction-gate/v1"`,
  which is inserted into `assessment_rule_versions` at startup with its parameters (the threshold
  and the routing field list).
- `processing_trace_steps`: new `TraceStep` values `DOCUMENTS_ATTACHED` (detail: the count of
  documents) and `EXTRACTION_CHECKED` (detail: `routed` or `clear`, plus counts; no values).

---

## Accuracy report (files, not tables)

`data/reports/extraction/<run-id>-<UTC timestamp>/extraction-accuracy.json` (format in
[contracts/accuracy-report.md](./contracts/accuracy-report.md)):

- `format`: `extraction-accuracy/1`
- `created_at`, `run_id`, `pack_ids`, `limit`, `confidence_threshold`
- `methods`: per document type, the method id and versions
- `fields[]`: `document_type`, `field` (index-free path), `matched`, `mismatched`, `not_found`,
  `total`, `match_rate`, `mismatching_packs[]`
- `documents[]`: per document type, the totals, the match rate, the failed count and the
  uncertain count
- `timing`: total seconds, mean seconds per pack, and the slowest step

A Markdown rendering (`extraction-accuracy.md`) is written beside it for humans. Personal values
never appear in either file. Mismatches name the pack id and field only. The `pack` subcommand
prints values, because generated packs are fictional and the developer asked for that pack.
