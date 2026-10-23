# Implementation Plan: Application Walking Skeleton

**Branch**: `001-application-walking-skeleton` | **Date**: 2026-10-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-application-walking-skeleton/spec.md`

## Summary

Build the thinnest end-to-end path for a social support application: form, then validation, then
assessment, then a stored, explained decision shown to the user. Previous decisions can be looked
up with the reference number and Emirates ID, and caseworkers see a passcode-protected review
queue.

The system is a FastAPI service with a Streamlit thin client. Data is persisted in SQLite through
SQLAlchemy and is Postgres-ready. The assessment is a placeholder income-per-member rule behind an
`Assessor` protocol, so features 005 (ML) and 006 (agents) can replace it without changing the
API, the storage, or the UI.

## Technical Context

**Language/Version**: Python 3.12, with the environment and dependencies managed by `uv`
(`pyproject.toml` + `uv.lock`, pinned by `.python-version`).

**Primary Dependencies**:
- `fastapi` and `uvicorn`: the API
- `pydantic` v2 and `pydantic-settings`: request schemas and configuration
- `sqlalchemy` 2.x: the ORM
- `streamlit`: the UI
- `httpx`: the UI's API client
- Dev only: `pytest`, `ruff`

**Storage**: SQLite file (`data/app.db`) through SQLAlchemy. Changing `DATABASE_URL` points it at
PostgreSQL. Tables are created at startup; Alembic is deferred (see research R11).

**Testing**:
- pytest: unit, contract and integration tests
- FastAPI `TestClient` with in-memory SQLite
- `streamlit.testing.v1.AppTest` for a UI smoke test

**Target Platform**: a local Windows 11 laptop (CPU only, about 15 GB RAM, no Docker). Both
processes run on localhost.

**Project Type**: a web application (API service plus a thin UI client), structured as a single
Python package.

**Performance Goals**: the result is shown within 5 s for 95% of submissions (SC-002). With a rule
assessor and SQLite, that is expected to be under 200 ms.

**Constraints**: works offline; no external network calls. The Emirates ID and income never appear
in logs or URLs. Records are append-only.

**Scale/Scope**: a single demo user; tens to hundreds of applications; 3 UI screens and 4 API
endpoints.

No NEEDS CLARIFICATION items remain. The user fixed the stack, and the remaining design choices
are resolved in [research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Pre-research | Post-design | Evidence |
|---|---|---|---|
| I. Local-first & privacy | PASS | PASS | No LLM and no network calls. Synthetic data only. Emirates ID kept out of URLs and logs (R6, R9) |
| II. Explainable decisions | PASS | PASS | `AssessmentResult` requires an explanation and rule version for every outcome, including the fallback (R2, data-model) |
| III. Human-in-the-loop | PASS | PASS | No hard decline value exists. Borderline cases and failures go to `NEEDS_HUMAN_REVIEW`. Thresholds are configurable (R3, R10) |
| IV. Fairness & auditability | PASS | PASS | No protected attributes collected. `ApplicationInput` excludes identity. Decisions are append-only and reference a rule version (R3, R8). The model evaluation report doesn't apply until feature 005 (there is no model yet) |
| V. Test-first for decision logic | PASS | PASS | Validation and rule boundary tests are written first. A fake `Assessor` covers the failure path (R12). "Agents testable with a mocked LLM" doesn't apply because there are no agents yet |
| VI. Swappable infrastructure | PASS | PASS | `DATABASE_URL`, an `Assessor` protocol with a factory chosen by `ASSESSOR`, a repository layer, and all configuration in settings (R2, R11) |
| VII. End-to-end observability | PASS (partial, justified) | PASS (partial, justified) | Per-application trace steps and structured JSON logs (R9). Agent and LLM tracing isn't needed yet; Langfuse arrives in feature 008. See Complexity Tracking |
| VIII. Simplicity & thin slices | PASS | PASS | One package, two processes, no migrations tool, no auth framework. Every story can be demonstrated independently |

**Gate result: PASS.** One partial item (VII) is recorded below.

## Project Structure

### Documentation (this feature)

```text
specs/001-application-walking-skeleton/
├── spec.md              # Feature spec (clarified)
├── plan.md              # This file
├── research.md          # Phase 0: design decisions R1–R13
├── data-model.md        # Phase 1: entities, rule logic
├── quickstart.md        # Phase 1: validation & demo guide
├── contracts/
│   └── api.md           # Phase 1: REST contract v1
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
pyproject.toml                 # uv project; ruff + pytest config
.python-version                # 3.12
.env.example                   # documented settings (no secrets)

src/social_support/
├── config.py                  # pydantic-settings: DB URL, passcode, assessor, rule params
├── domain/
│   ├── models.py              # enums, ApplicationInput, AssessmentResult (pure, no I/O)
│   ├── validation.py          # Emirates ID normalisation, field rules
│   └── assessor.py            # Assessor protocol + factory
├── assessment/
│   └── income_rule.py         # IncomePerMemberRuleAssessor (v0.1)
├── persistence/
│   ├── db.py                  # engine/session from DATABASE_URL, create_all
│   ├── orm.py                 # SQLAlchemy models (4 tables)
│   └── repository.py          # add/get only — no update/delete
├── services/
│   ├── applications.py        # submit / lookup / review-queue orchestration, fallback, duplicates
│   ├── reference.py           # SSA- reference generator
│   └── tracing.py             # trace step recorder + JSON logging setup
├── api/
│   ├── main.py                # FastAPI app, startup (create_all, rule version registration)
│   ├── schemas.py             # request/response models per contracts/api.md
│   ├── errors.py              # flat errors[] 422 handler
│   └── routes.py              # 4 endpoints + passcode dependency
└── ui/
    ├── app.py                 # Streamlit entry: Apply / Look up / Review queue
    └── client.py              # httpx wrapper over the API

tests/
├── conftest.py                # in-memory DB, TestClient, fake assessors
├── fixtures/synthetic_applications.py   # ≥20 cases for SC-005
├── unit/                      # validation, rule boundaries, reference format
├── contract/                  # endpoint shapes & status codes vs contracts/api.md
├── integration/               # full path, lookup security, duplicates, failure fallback, review auth
└── ui/                        # Streamlit AppTest smoke test
```

**Structure Decision**: a single `src/`-layout package (`social_support`) with layered
subpackages. The order of layers is `domain` → `assessment` / `persistence` → `services` → `api`;
`ui` depends only on the HTTP API.

The template's "Option 2: backend/ + frontend/" layout was rejected because both halves are Python
and share one dependency set; splitting them would add a second project with no benefit
(Principle VIII). The `ui` package imports nothing from the other layers, which keeps the boundary
enforceable. A test asserts this.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle VII is only partly met: no Langfuse or agent tracing in this slice | There are no agent or LLM calls to trace yet. Self-hosted Langfuse needs Docker, which this machine doesn't have | Adding Langfuse now would trace nothing that the `processing_trace_steps` table and JSON logs don't already capture. It is planned for feature 008, wrapping `Assessor.assess()` |
| Two processes (API + UI) instead of one Streamlit app | Keeps an explicit, testable API contract for later integrations (R1) | An in-process Streamlit app would merge UI and domain code and hide the integration surface the brief evaluates |
