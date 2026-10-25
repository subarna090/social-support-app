# Implementation Plan: Document Extraction

**Branch**: `003-document-extraction` | **Date**: 2026-10-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-document-extraction/spec.md`

## Summary

Applicants attach the five documents in the Apply form. The API stores each original unchanged in
a draft, and reads it in the background on a single-worker queue in the API process:

| Document | Method |
|---|---|
| Bank statement, credit report | label-anchored parsers over `pypdf` text. The credit/debit column is recovered from the running balance |
| Assets and liabilities spreadsheet | parsed with `openpyxl` |
| Emirates ID card image | **RapidOCR** on a 2× upscaled image, with label geometry and format checks |
| Resume | contact details by pattern; the employment and education sections by **`qwen2.5:7b`** through Ollama, using a compact line protocol in which every value must appear in the text |

Every value carries its source document, a confidence and an uncertain flag (threshold 0.80,
configurable).

The form shows the read-only extracted values and highlights covered form fields that differ from
their documents (server-side comparison). Submission needs all five documents, each read or failed.
On submit, the documents, extraction results and fields become append-only rows in the same
transaction as the application and decision. A versioned **extraction gate** (`extraction-gate/v1`)
routes the case to Needs Human Review when a document failed or a **routing field** is uncertain.
Otherwise the 001 assessor decides exactly as before.

Caseworkers can open any application by reference number and see the originals, the values and the
flags. A new CLI, `social-support-extract`, measures field-level accuracy against the feature 002
answer keys (20 packs by default, about 10 minutes) and writes the fixed set of broken demo files.
Seeding now uploads documents.

## Technical Context

**Language/Version**: Python 3.12, managed by `uv`. This extends the existing `social_support`
package.

**Primary Dependencies**:
- New runtime: `rapidocr_onnxruntime` (with `onnxruntime`, `opencv-python` and `numpy`)
- Promoted from dev to runtime: `pypdf`
- Reused: FastAPI, with `python-multipart` for uploads; SQLAlchemy; Streamlit (`st.fragment`
  polling, `st.file_uploader`); `httpx` for the Ollama HTTP API (no `ollama` SDK); `openpyxl`;
  `pillow`
- Local services: Ollama with `qwen2.5:7b`

**Storage**: SQLite through SQLAlchemy, as before; PostgreSQL remains a config swap. New tables:
mutable `drafts` and `draft_documents`, content-addressed `document_contents` (originals as
`LargeBinary`), and append-only `application_documents`, `extraction_results` and
`extracted_fields`. Reports are files under `data/reports/extraction/` (git-ignored).

**Testing**: pytest.
- **Default suite**: fake OCR and LLM injected through `create_app(…, extractors=…)`; real PDF and
  xlsx parsers on packs generated into `tmp_path`. No models needed.
- **New `models` marker**: real RapidOCR and Ollama; skipped when they are unavailable.
- **`slow` + `models`**: the 20-pack accuracy run.

**Target Platform**: the local Windows 11 laptop (CPU only, about 15 GB RAM, no Docker). Offline
apart from local Ollama.

**Project Type**: web service (FastAPI) + Streamlit UI + CLI, in the existing single Python
project.

**Performance Goals**: measured on the reference laptop (research R5, R6):

| Target | Expected |
|---|---|
| One applicant's five documents read within 2 minutes (SC-003) | about 25–35 s: resume 13–25 s, ID card about 6 s, others under 1 s |
| 20-pack accuracy report in under 15 minutes (SC-009) | about 10 minutes |
| OCR engine start-up | about 13 s, warmed in the background at API start |

**Constraints**:
- No document, text or value leaves the machine (FR-006).
- Uploads are capped at 10 MB, and the file type is detected from the leading bytes.
- Logs carry no document content or personal values (FR-021).
- Draft ids are bearer secrets and are never logged.
- RAM: OCR about 300 MB, plus `qwen2.5:7b` about 5 GB in Ollama.

**Scale/Scope**:
- 5 extractors, 1 routing gate, 7 new API endpoints (5 for drafts, 2 for caseworkers) plus 2
  changed ones (submit, `/health`), 1 new CLI with 3 subcommands
- Seeding and the Apply and Review UI change
- A few concurrent applicants. Jobs are processed one at a time, in order

No NEEDS CLARIFICATION items remain. The user fixed RapidOCR and local `qwen2.5`. The spec
clarifications (2026-10-24 and 2026-10-25) settled scope, mandatory documents, the 20-pack
default, routing fields, broken fixtures, caseworker access and draft reloads. Everything else is
resolved in [research.md](./research.md) (R1–R22).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Pre-research | Post-design | Evidence |
|---|---|---|---|
| I. Local-first & privacy | PASS | PASS | All reading runs locally: pypdf, openpyxl, RapidOCR (ONNX on CPU), and Ollama at `127.0.0.1` (R2–R6). No hosted API. Only synthetic packs are used. Originals are stored in the local DB (R13). Drafts expire after 24 h (R12). Logs have no content or values (R22) |
| II. Explainable decisions | PASS | PASS | Every value names its source document and can be traced to the stored original (FR-003, data-model `extracted_fields` → `application_documents`). Gate decisions have a plain explanation that names `extraction-gate/v1` (R14). Grounding stops invented values (R9) |
| III. Human-in-the-loop | PASS | PASS | Failed documents and uncertain routing fields route the case to Needs Human Review (FR-019, R14). The threshold is an explicit setting (R8). An unavailable LLM gives a failed document, never a guess (R5). The caseworker view shows everything (FR-020). There is still no hard decline |
| IV. Fairness & auditability | PASS | PASS | Nationality and sex are extracted only because FR-002 lists them. They are stored, never used for routing, comparison or assessment, and assessors still see only family size, income and employment (architecture test). Every extraction stores its method, versions (LLM digest, OCR version) and threshold (FR-017). The gate is a versioned rule row. The accuracy report records the batch and versions (FR-024) |
| V. Test-first for decision logic | PASS | PASS | Written test-first: the gate, the routing-field set, confidence and threshold, normalisation and comparison, the running-balance rule, grounding and accuracy scoring (R20). The LLM sits behind a protocol, with a fake for control-flow tests. An end-to-end test (generate a pack → draft → upload → submit → caseworker view) runs on synthetic data |
| VI. Swappable infrastructure | PASS | PASS | `DocumentExtractor`, `OcrEngine` and `TextLlm` protocols. Ollama (URL, model, timeout), the threshold, the TTL, the size cap and the worker count all come from settings. Vendor libraries stay in `extraction/` adapters (R1). Blobs stay in the DB, behind repositories (R13). The queue sits behind `ExtractionQueue` (R11) |
| VII. End-to-end observability | PASS (partial, justified) | PASS (partial, justified) | Extraction results store per-step timings, including the LLM call (model, token counts, duration) (R22). New trace steps `DOCUMENTS_ATTACHED` and `EXTRACTION_CHECKED`. Structured logs use whitelisted keys. Prompt and output tracing goes to Langfuse in feature 008, carried over from 001 and 002 |
| VIII. Simplicity & thin slices | PASS | PASS | No new service or broker: an in-process executor (R11) and the DB for blobs (R13). The LLM is used only where the text is free-form (R5). Each story can be demonstrated alone (quickstart). The new complexity (drafts as mutable state, a background queue) is justified below |
| Gate: `/speckit-analyze` before implement | n/a | pending | Runs after `/speckit-tasks` |

**Gate result: PASS.** Principle VII is still partial for the same reason as in 001 and 002; see
Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-document-extraction/
├── spec.md                    # Feature spec (clarified: 6 Q&As)
├── plan.md                    # This file
├── research.md                # Phase 0: decisions R1–R22, with measured timings
├── data-model.md              # Phase 1: domain types, draft tables, append-only tables, report
├── quickstart.md              # Phase 1: validation guide + 13-step demo script
├── contracts/
│   ├── api.md                 # drafts, comparison, submit (changed), caseworker view, health
│   ├── cli.md                 # social-support-extract accuracy | pack | broken-samples; seed (changed)
│   ├── field-catalogue.md     # fields per document, answer-key mapping, routing/covered flags
│   └── accuracy-report.md     # extraction-accuracy/1 JSON format
├── checklists/
│   └── requirements.md        # Spec quality checklist (16/16)
└── tasks.md                   # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
pyproject.toml                 # + rapidocr_onnxruntime; pypdf → runtime; script social-support-extract;
                               #   pytest marker "models"
.env.example                   # + OLLAMA_BASE_URL, EXTRACTION_LLM_MODEL, EXTRACTION_LLM_TIMEOUT_S,
                               #   EXTRACTION_CONFIDENCE_THRESHOLD, EXTRACTION_WORKERS, DRAFT_TTL_HOURS,
                               #   MAX_DOCUMENT_MB, EXTRACTION_OCR_SCALE

src/social_support/
├── config.py                  # + extraction settings (above)
├── domain/
│   ├── extraction.py          # NEW: DocumentType, DocumentStatus, FieldKind, ExtractedField,
│   │                          #   DocumentExtraction, DocumentExtractor protocol, CoveredField,
│   │                          #   FieldComparison, build_extractors() (lazy imports)
│   ├── normalise.py           # NEW: canonical forms for text/money/date/month/Emirates ID (R10)
│   └── models.py              # + TraceStep.DOCUMENTS_ATTACHED, EXTRACTION_CHECKED
├── extraction/                # NEW layer (R1): may import domain, config, services.tracing only
│   ├── __init__.py            # EXTRACTION_VERSION
│   ├── __main__.py            # python -m social_support.extraction
│   ├── catalogue.py           # field catalogue (contracts/field-catalogue.md)
│   ├── filetypes.py           # detection from leading bytes, size cap (R12)
│   ├── pdf_text.py            # pypdf reading + marking/page-footer clean-up (R2)
│   ├── confidence.py          # scores + threshold application (R8)
│   ├── grounding.py           # "value appears in the text" check (R9)
│   ├── bank_statement.py      # parser + running-balance rule (R3)
│   ├── credit_report.py       # parser (R3)
│   ├── assets_liabilities.py  # openpyxl reader (R4)
│   ├── emirates_id.py         # OCR label geometry + format checks (R6)
│   ├── ocr.py                 # OcrEngine protocol + RapidOcrEngine (lazy load, warm-up)
│   ├── resume.py              # contact parser + LLM sections + line protocol (R5)
│   ├── llm.py                 # TextLlm protocol + OllamaLlm (httpx; temperature 0, seed, keep_alive)
│   ├── comparison.py          # covered-field comparison (R15)
│   ├── gate.py                # extraction gate → problems, routed? (R14)
│   ├── evaluation.py          # accuracy scoring + report writer (R17)
│   ├── broken_samples.py      # the R18 set, shared by tests and the CLI
│   └── cli.py                 # social-support-extract accuracy | pack | broken-samples
├── persistence/
│   ├── orm.py                 # + DraftRow, DraftDocumentRow, DocumentContentRow,
│   │                          #   ApplicationDocumentRow, ExtractionResultRow, ExtractedFieldRow
│   ├── repository.py          # ApplicationRepository: + add documents/extraction in add_submission,
│   │                          #   get documents/content (still add/get only)
│   └── drafts.py              # NEW DraftRepository (mutable: draft tables only) + expiry purge
├── services/
│   ├── drafts.py              # NEW DraftService: create, attach/replace/remove, status, comparison
│   ├── extraction_queue.py    # NEW ExtractionQueue (ThreadPoolExecutor, generation check, recovery)
│   ├── applications.py        # submit(draft_id, …): refusals, gate, copy draft → append-only;
│   │                          #   caseworker_view(reference)
│   └── tracing.py             # + whitelisted keys: draft_ref, document_type, extraction_status,
│                              #   method, duration_ms, count
├── api/
│   ├── main.py                # create_app(settings, assessor=None, extractors=None); lifespan starts
│   │                          #   the queue, OCR warm-up, expiry task, startup recovery, gate rule row
│   ├── routes.py              # + draft, comparison, caseworker endpoints; submit takes draft_id
│   └── schemas.py             # + DraftOut, DocumentOut, FieldOut, ComparisonIn/Out, CaseworkerView
├── ui/
│   ├── app.py                 # Apply without st.form: 5 uploaders, progress fragment, read-only
│   │                          #   values, highlights, guarded submit; Review: + Open application
│   └── client.py              # + create_draft, upload_document, remove_document, get_draft,
│                              #   compare, caseworker_application, caseworker_document
└── synthetic/
    └── seeding.py             # draft → upload 5 → wait → submit; report columns (R19)

tests/
├── conftest.py                # make_client(assessor=…, extractors=…); FakeExtractors; submit helper
├── fixtures/
│   ├── broken_documents.py    # wraps extraction.broken_samples for tests (R18)
│   └── extraction_text/       # stored pypdf text of a few generated documents, for parser unit tests
├── unit/                      # normalise, filetypes, each parser, OCR geometry (canned boxes),
│                              #   resume line protocol + grounding (fake LLM), confidence, gate,
│                              #   comparison, evaluation scoring, catalogue ↔ contract, architecture
├── contract/                  # drafts, comparison, submit (changed), caseworker view, health
├── integration/               # draft lifecycle, replace/stale generation, refusals, storage +
│                              #   append-only, expiry, recovery, seeding over in-process HTTP,
│                              #   real parsers on generated packs
├── models/                    # @models: real RapidOCR/Ollama; 5-pack accuracy; @slow 20-pack run
├── ui/                        # smoke: uploaders, progress, highlight, disabled submit, caseworker view
└── e2e/                       # generate → draft → upload → submit → caseworker view
```

**Structure Decision**: a new `extraction/` layer beside `assessment/`. Both are implementations
behind domain protocols, built by factories in `domain`. Draft use cases go in `services/drafts.py`
and the queue in `services/extraction_queue.py`. Mutable draft storage is kept apart
(`persistence/drafts.py`), so `ApplicationRepository` stays add/get only. The architecture tests
gain rules for `extraction` and for `DraftRepository` being the only repository with update or
delete methods. Existing 001 and 002 tests that submit form-only bodies move to a shared helper
that creates a draft with fake extraction first (FR-025).

## Complexity Tracking

| Violation or added complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| Mutable draft tables and a repository with update/delete, next to the append-only rule | Applicants replace or remove documents and see the status change before submitting (FR-007, FR-008), and unsubmitted drafts must be deleted (FR-014) | Making drafts append-only would keep personal documents past 24 h, which breaks FR-014 and Principle I. Keeping drafts only in UI memory would put extraction in the UI, which must talk only to the API |
| In-process background queue (`ThreadPoolExecutor`) with a generation check and startup recovery | Extraction takes about 30 s, and the applicant must keep typing (FR-008) | Extracting synchronously would block the request past HTTP timeouts. A broker or worker process (Celery, RQ) is an extra service on a laptop with no Docker (Principle VIII) |
| Hybrid resume extractor (pattern-based contacts + LLM sections + line protocol) instead of "LLM reads the resume" | Measured: whole-resume JSON took 55–84 s and the smaller model made errors. The line protocol is 3–4× faster and correct (R5) | Pure LLM would miss SC-009 (20 packs in under 15 minutes). A pure parser would leave no LLM for free-form text, which the brief requires |
| Principle VII partial: no LLM prompt and output tracing to Langfuse yet | Feature 008 owns Langfuse. This feature records the model, token counts and durations per call (R22) | Adding Langfuse now would widen this slice and needs the 008 privacy design for content capture |
