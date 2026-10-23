# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Feature 001 (walking skeleton) is implemented: an application form produces a stored, explained decision; lookup by reference number plus Emirates ID; a passcode-protected caseworker review queue. The assessment is a placeholder rule. The brief (`AI Case Study_DGE 5 - Copy.docx`) is kept locally and is git-ignored.

## Commands

```powershell
uv sync                                              # install (uv fetches Python 3.12)
uv run pytest                                        # all tests (~5 s)
uv run pytest tests/unit/test_income_rule.py         # one file
uv run pytest tests/integration/test_submit_flow.py::test_duplicate_emirates_id_is_accepted_and_noted   # one test
uv run pytest -k lookup                              # by keyword
uv run ruff check . ; uv run ruff format .           # lint / format (line length 100)
uv run uvicorn social_support.api.main:app           # API, docs at http://127.0.0.1:8000/docs
uv run streamlit run src/social_support/ui/app.py    # UI at http://localhost:8501
```

Configuration comes from `.env` (see `.env.example`). `CASEWORKER_PASSCODE` must be set or the review queue always returns 401. On Windows, `uvicorn --reload` can hang mid-reload and keep serving old routes; restart the server if an endpoint seems missing.

## Architecture

The `src/social_support/` layers, with dependencies pointing inward only. `tests/unit/test_architecture.py` enforces this:

- `domain/`: pure types (`Outcome`, `ApplicationInput`, `AssessmentResult`), validation rules and messages, and the `Assessor` protocol with its `build_assessor()` factory. No framework or storage imports.
- `assessment/`: `Assessor` implementations. Currently only `IncomePerMemberRuleAssessor` (v0.1). **This is the extension point:** ML (feature 005) and agent (feature 006) assessors are added here and selected with the `ASSESSOR` setting. Every assessor must return an explanation and a rule version. Assessors see only family size, income and employment status, never identity.
- `persistence/`: SQLAlchemy 2.x ORM (4 append-only tables) and `ApplicationRepository`, which has **add and get methods only**. Never add update or delete methods (FR-009). Tables are created at startup with `create_all`; there are no migrations yet.
- `services/`: use cases in `ApplicationService` (submit, lookup, review_queue), reference generation, and tracing (a JSON log formatter with a whitelist of allowed keys, and `TraceRecorder`). If assessment fails, the fallback is `NEEDS_HUMAN_REVIEW` with the rule version `fallback`.
- `api/`: the FastAPI app factory `create_app(settings, assessor=None)`, routes under `/api/v1`, and schemas. Routes call services, never ORM models. Validation errors use a flat `{"errors": [{field, message}]}` shape.
- `ui/`: Streamlit. It talks to the API **only over HTTP** through `ui/client.py`, and must not import other `social_support` packages.

Conventions that are easy to break:
- Never log Emirates IDs, names or incomes. Add only whitelisted `extra` keys (`services/tracing.py`).
- Money is a `Decimal` internally and a 2-dp string in JSON. Timestamps are UTC ISO strings ending in `Z` (`api/schemas.iso_utc`), because SQLite drops tzinfo.
- A missing reference and a mismatched Emirates ID on lookup must stay indistinguishable (identical 404 body).
- FastAPI 0.161 hides included routers from `app.routes`. Inspect endpoints with `app.openapi()["paths"]` instead.
- Tests use `make_client(assessor=..., **settings)` from `tests/conftest.py`, which gives an in-memory SQLite database and the passcode `test-passcode`. Synthetic cases are in `tests/fixtures/synthetic_applications.py`.

## Spec-driven workflow (Spec Kit)

This project is built with GitHub Spec Kit (`specify` CLI 1.2.0, PowerShell scripts). The commands are installed as skills in `.claude/skills/`. The user is learning Spec Kit, so follow the flow rather than writing code ad hoc:

`/speckit-constitution` → per feature: `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-checklist` (optional) → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`

- Project principles live in `.specify/memory/constitution.md`. Every plan must pass its gates.
- Each feature gets a branch and a folder `specs/NNN-feature-name/` (`spec.md`, `plan.md`, `data-model.md`, `contracts/`, `tasks.md`).
- `spec.md` covers *what/why* only. Technology choices belong in `plan.md`.
- Build in thin vertical slices: 001 is a walking skeleton, then synthetic data, extraction, validation, eligibility ML, agent orchestration, chat/enablement, observability.

## Local environment constraints

- Windows, CPU only (no GPU), 15 GB RAM. No Docker, no local Postgres.
- Ollama models: `qwen2.5:7b` (main), `qwen2.5:3b` (fast fallback), `nomic-embed-text` (embeddings). Prefer OCR (Tesseract/EasyOCR) over vision LLMs for ID images.
- Use SQLite through SQLAlchemy for now so that Postgres is a config swap later. ChromaDB runs embedded.
- Python is managed with `uv`.

## What is being built

A prototype that automates a government social security department's application workflow. The current process takes 5–20 working days; the goal is near-100% automated decisions within minutes, with live interaction through a GenAI chatbot.

The system must:
- Ingest an interactive application form plus attachments: bank statement, Emirates ID (image), resume, assets/liabilities Excel file, and credit report. Synthetic or mock data is acceptable.
- Validate and reconcile inconsistencies across documents (e.g. address on the form vs. the credit report, income across financial documents, family member details).
- Assess eligibility on income level, employment history, family size, wealth, and demographic profile.
- Recommend **approve or soft decline** for financial support.
- Recommend **economic enablement** support: upskilling/training, job matching, career counseling.

## Hard requirements from the brief

- **Locally hosted** ML and LLM models (Ollama, LM Studio, OpenWebUI, or LLMWare). No hosted LLM APIs.
- **Multimodal** processing and storage: text, images, tabular data.
- **Interactive chat** UI in Streamlit or Gradio.
- **Agentic orchestration** (LangGraph, LlamaIndex, Phidata, or CrewAI) with these agents: master orchestrator, data extraction, data validation, eligibility check, decision recommendation.
- At least one **agent reasoning framework**: ReAct, Reflexion, Plan-and-Solve, etc.
- **Scikit-learn classifier** for eligibility. The choice of algorithm must be justified in terms of the data's characteristics.
- **Observability** through Langfuse or LangSmith, end to end.
- **Model serving** with FastAPI, Flask, Ollama, LM Studio, or OpenWebUI.
- Language: Python. Data stack: Pandas, LlamaIndex, ChromaDB (vectors), PostgreSQL (structured records).

## Deliverables

- Source in a private GitHub repo.
- `README.md` with clear step-by-step run instructions.
- Solution summary (≤10 pages) covering: an architecture diagram with data flow, tool choices justified on suitability, scalability, maintainability, performance and security, a modular breakdown of the AI workflow, and future improvements and integration (API design, data pipelines).

Evaluation weighs functionality against sections 2–4 of the brief, code modularity and documentation, solution design, integration quality (APIs and pipelines), demo UI usability, and communication.
