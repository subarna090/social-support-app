# Implementation Plan: PoC Demo — Documents to Decision and Enablement

**Branch**: `004-poc-demo` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-poc-demo/spec.md`

## Summary

The applicant submits the 001 form plus five files in one multipart request. The API:
1. stores the files and extracts their fields with local, non-LLM tools (pypdf text plus regex for
   the three PDFs, RapidOCR for the ID card image, openpyxl for the spreadsheet);
2. runs four pure cross-checks (name and ID number against the ID card, name against the bank
   account holder, declared income against bank income credits). The service turns failed checks
   and unreadable documents into review findings, so the assessor never sees identity;
3. evaluates a new versioned TOML rule set with **every** rule checked independently, so all
   reasons are reported. Each matching rule is a finding with an outcome. The worst outcome wins
   (review > soft decline > approve), and failed cross-checks or unreadable documents are review
   findings;
4. stores everything append-only and returns the decision with reasons, cross-checks and extracted
   values.

The UI then makes a second call for the enablement plan. The local Ollama model (`qwen2.5:7b`)
produces it from an anonymised profile, and a fixed fallback is used when the model fails, so the
decision never waits for the LLM. A new `social-support-data demo` command writes three fixed packs
(approve, soft_decline, review) using the 002 renderers.

## Technical Context

**Language/Version**: Python 3.12 (uv)

**Primary Dependencies**: existing FastAPI, SQLAlchemy 2, Streamlit, httpx, openpyxl, reportlab,
Pillow. New: `pypdf` (moved from dev to runtime), `rapidocr-onnxruntime` 1.4.x (models bundled in the
wheel, CPU, works offline), `python-multipart` (FastAPI file uploads). Ollama is called over HTTP with
the existing `httpx`, so no SDK is needed.

**Storage**: SQLite through SQLAlchemy (existing). Five new append-only tables. Uploaded files are
stored on disk under `UPLOAD_DIR` (default `data/uploads/<reference>/`), with their SHA-256 in the database.

**Testing**: pytest. Unit tests for parsers on text fixtures, cross-checks and decision rules
(written first). Integration tests for extraction against the demo packs' answer keys (real OCR).
API contract tests with a fake enablement advisor. One end-to-end test that generates the three demo
packs and submits them through the API.

**Target Platform**: Windows 11 laptop, CPU only, 15 GB RAM. Ollama runs locally.

**Project Type**: web service + Streamlit UI + CLI (existing single project).

**Performance Goals**: decision in under 30 s (measured: OCR 2.8 s per card plus 1.2 s one-time model
load; PDF parsing well under 1 s). Enablement within the 90 s timeout on `qwen2.5:7b`; `qwen2.5:3b` is a
config switch if the laptop is too slow.

**Constraints**: no LLM in extraction or the decision; no identity, exact income or protected
attributes sent to the LLM; no hard decline; append-only storage; 10 MB per file.

**Scale/Scope**: demo scale (a handful of applications). Extractors target the 002 document layout only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Local-first & privacy | PASS | OCR, PDF parsing and the LLM all run locally; the LLM profile excludes name, Emirates ID, exact income, nationality and gender; synthetic data only. |
| II Explainable decisions | PASS | Every finding carries its text, the compared values and the source documents; extracted values record their document. |
| III Human-in-the-loop | PASS | Failed cross-checks, unreadable documents, uncertain factors and low OCR confidence (`OCR_MIN_CONFIDENCE`, default 0.80) route to review; there is no hard decline; rule thresholds are in a versioned TOML, and the income tolerance and OCR threshold are env settings. |
| IV Fairness & auditability | PASS | Rules see only `HouseholdFacts` (no protected attributes, no identity: the assessor receives facts plus findings the service has already built, never documents). The decision is stored with its inputs (extracted values and the derived facts in `decision_inputs`), cross-checks, findings and the rule version. A group evaluation report applies only to the ML model (feature 005). |
| V Test-first | PASS | Cross-check and rule tests are written first; the LLM advisor is mocked in tests; an end-to-end test runs over the demo packs. |
| VI Swappable infrastructure | PASS | `EnablementAdvisor` and the extractors sit behind domain protocols; Ollama URL, model and timeout come from env; the database stays configurable. |
| VII Observability | PASS (tool deferred) | Every tool call and LLM call is traced with inputs, outputs, latency and the application: each document row stores its fields, confidence and `duration_ms`; the enablement row stores the profile sent, the plan returned and `latency_ms`; the trace steps EXTRACTED, CROSS_CHECKED and ENABLEMENT carry durations. A dedicated tracing tool (Langfuse) is deferred; see Complexity Tracking. |
| VIII Thin slices | PASS | One vertical slice from form to decision to enablement; no new services or frameworks. |
| Workflow | NOTE | `/speckit-clarify` was skipped by user decision (condensed flow); the scope answers are recorded in spec.md. |

**Post-design re-check (2026-10-26, after `/speckit-analyze`)**: all principles pass. Design changes
from the analysis: OCR confidence routing (III), an identity-free assessor input and stored decision
facts (IV), and persisted tool/LLM inputs, outputs and latency (VII). The only remaining exception is
the Langfuse tooling deferral below.

## Project Structure

### Documentation (this feature)

```text
specs/004-poc-demo/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.md          # multipart submit, enablement, review queue changes
│   └── cli.md          # social-support-data demo
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
src/social_support/
├── domain/
│   ├── documents.py        # NEW DocumentType, ExtractedDocument, CrossCheckResult, Finding
│   ├── crosschecks.py      # NEW pure cross-checks (form vs extracted documents)
│   ├── enablement.py       # NEW EnablementProfile, EnablementPlan, EnablementAdvisor protocol, FALLBACK_PLAN
│   └── models.py           # + TraceStep EXTRACTED / CROSS_CHECKED / ENABLEMENT
├── extraction/             # NEW non-LLM extractors (imports domain only)
│   ├── __init__.py         # extract_all(files) -> dict[DocumentType, ExtractedDocument]
│   ├── pdf_text.py         # pypdf -> text
│   ├── bank_statement.py
│   ├── credit_report.py
│   ├── resume.py           # skills, education, jobs, months employed, years of experience
│   ├── emirates_id.py      # RapidOCR (lazy singleton) + parse of OCR lines
│   └── assets_liabilities.py
├── labelling/
│   ├── policy.py           # + LabellingPolicy.evaluate_all(facts) -> list[LabelResult]
│   └── policies/decision_v1.toml   # NEW independent finding rules
├── assessment/
│   └── document_rules.py   # NEW DocumentRuleAssessor: (HouseholdFacts | None, pre-built findings) -> CaseAssessment; never sees documents or identity
├── enablement/             # NEW
│   └── ollama.py           # OllamaEnablementAdvisor (httpx, JSON mode, timeout, validation)
├── persistence/
│   ├── orm.py              # + DocumentRow, CrossCheckRow, FindingRow, DecisionInputsRow, EnablementPlanRow
│   └── repository.py       # + add/get for the new rows (no update/delete)
├── services/
│   ├── applications.py     # + submit_with_documents, enablement_for, review reasons
│   ├── uploads.py          # NEW file validation + storage under UPLOAD_DIR
│   └── tracing.py          # + whitelisted keys: document_type, check_id, model, is_fallback
├── api/
│   ├── routes.py           # + POST /applications/with-documents, POST /applications/{ref}/enablement
│   └── schemas.py          # + DocumentOut, CrossCheckOut, FindingOut, EnablementOut
├── ui/
│   ├── app.py              # Apply tab: form + 5 uploaders, decision, findings, extracted values, enablement
│   └── client.py           # + submit_with_documents, enablement (longer timeouts)
├── synthetic/
│   ├── demo.py             # NEW three hand-built profiles -> data/demo/{approve,soft_decline,review}
│   └── cli.py              # + `demo` subcommand
└── config.py               # + UPLOAD_DIR, INCOME_TOLERANCE_PCT, OCR_MIN_CONFIDENCE, OLLAMA_URL, ENABLEMENT_MODEL, ENABLEMENT_TIMEOUT_S

tests/
├── unit/        test_crosschecks.py, test_decision_rules.py, test_parsers.py, test_enablement_advisor.py
├── integration/ test_extraction_demo_packs.py, test_submit_with_documents.py, test_enablement_flow.py
├── contract/    test_documents_contract.py
└── e2e/         test_demo_packs_end_to_end.py
```

**Structure Decision**: keep the single project and its inward-only layering. `extraction/` and
`enablement/` are new outer adapter packages: they may import `domain` (and `extraction` may import
`labelling.facts.money`), never `persistence`, `services`, `api` or `ui`. Only `services` wires them
together. The architecture test gains guards for both packages.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| VII: no Langfuse/LangSmith tool in this slice (the required trace content is stored in the database) | Demo this week; there are no agents yet, and the database rows plus JSON logs hold the inputs, outputs, latency and application of every tool and LLM call | Adding Langfuse now means extra setup and accounts and adds risk to the demo; it is planned as its own slice after agent orchestration |
| The old JSON `POST /applications` stays (no documents, `ASSESSOR` placeholder) | The 002 `seed` command and 001 tests use it | Removing it would break 002 seeding; the UI no longer calls it, so FR-002 holds for applicants (spec Assumptions) |
