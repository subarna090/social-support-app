# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Feature 001 (walking skeleton) is implemented: an application form produces a stored, explained decision; lookup by reference number plus Emirates ID; a passcode-protected caseworker review queue. The assessment is a placeholder rule. Feature 002 (synthetic data generator) adds the `social-support-data` CLI: reproducible fictional applicant packs (form, five documents, answer key), recorded cross-document inconsistencies, a labelled `summary.csv`, and seeding the running API. Feature 004 (PoC demo, condensed Spec Kit flow) adds the document path the UI uses: form plus five uploads → non-LLM extraction (pypdf, RapidOCR, openpyxl) → four cross-checks → `decision_v1.toml` findings → APPROVE / SOFT_DECLINE / NEEDS_HUMAN_REVIEW with every reason, then an LLM (Ollama) economic enablement plan with a labelled fallback, plus `social-support-data demo` for three fixed demo applicants. Feature 003 (fuller extraction design) lives only on its own branch. The brief (`AI Case Study_DGE 5 - Copy.docx`) is kept locally and is git-ignored.

## Commands

```powershell
uv sync                                              # install (uv fetches Python 3.12)
uv run pytest                                        # all tests except slow ones (~3 min; real OCR)
uv run pytest -m slow                                # 200-pack volume checks + 100-pack timing (~3 min)
uv run pytest tests/unit/test_income_rule.py         # one file
uv run pytest tests/integration/test_submit_flow.py::test_duplicate_emirates_id_is_accepted_and_noted   # one test
uv run pytest -k lookup                              # by keyword
uv run ruff check . ; uv run ruff format .           # lint / format (line length 100)
uv run uvicorn social_support.api.main:app           # API, docs at http://127.0.0.1:8000/docs
uv run streamlit run src/social_support/ui/app.py    # UI at http://localhost:8501
uv run social-support-data generate --count 10 --seed 42          # synthetic packs -> data/synthetic/<run-id>/
uv run social-support-data seed --run data/synthetic/<run-id>     # submit a run to the running API
uv run social-support-data demo [--force]                         # 3 demo applicants -> data/demo/{approve,soft_decline,review}
uv run pytest tests/e2e/test_demo_packs_end_to_end.py             # 004 end to end (real OCR, fake LLM)
```

Configuration comes from `.env` (see `.env.example`). `CASEWORKER_PASSCODE` must be set or the review queue always returns 401. On Windows, `uvicorn --reload` can hang mid-reload and keep serving old routes; restart the server if an endpoint seems missing.

## Architecture

The `src/social_support/` layers, with dependencies pointing inward only. `tests/unit/test_architecture.py` enforces this:

- `domain/`: pure types (`Outcome`, `ApplicationInput`, `AssessmentResult`), validation rules and messages, and the `Assessor` protocol with its `build_assessor()` factory. No framework or storage imports.
- `assessment/`: `Assessor` implementations. Currently only `IncomePerMemberRuleAssessor` (v0.1). **This is the extension point:** ML (feature 005) and agent (feature 006) assessors are added here and selected with the `ASSESSOR` setting. Every assessor must return an explanation and a rule version. Assessors see only family size, income and employment status, never identity.
- `persistence/`: SQLAlchemy 2.x ORM (4 append-only tables) and `ApplicationRepository`, which has **add and get methods only**. Never add update or delete methods (FR-009). Tables are created at startup with `create_all`; there are no migrations yet.
- `services/`: use cases in `ApplicationService` (submit, lookup, review_queue), reference generation, and tracing (a JSON log formatter with a whitelist of allowed keys, and `TraceRecorder`). If assessment fails, the fallback is `NEEDS_HUMAN_REVIEW` with the rule version `fallback`.
- `api/`: the FastAPI app factory `create_app(settings, assessor=None, advisor=None)`, routes under `/api/v1`, and schemas. Routes call services, never ORM models. Validation errors use a flat `{"errors": [{field, message}]}` shape.
- `ui/`: Streamlit. It talks to the API **only over HTTP** through `ui/client.py`, and must not import other `social_support` packages.
- `labelling/`: `HouseholdFacts` and the labelling policy loader/evaluator; policies are versioned TOML in `labelling/policies/` (ordered rules, first match wins; the version id hashes the file with line endings normalised). Pure: imports only `domain`, because feature 005 trains on these labels. Facts never include identity or protected attributes.
- Feature 004 additions:
  - `domain/documents.py` (`DocumentType`, `ExtractedDocument`, `CrossCheckResult`, `Finding`, `CaseAssessment`), `domain/crosschecks.py` (pure form-vs-document checks) and `domain/enablement.py` (`EnablementProfile`, `EnablementPlan`, the `EnablementAdvisor` protocol, `FALLBACK_PLAN`).
  - `extraction/`: `extract_all()` with one parser per document. It is an adapter layer that imports `domain` only. A failure in one document becomes `ok=False` and never raises. The credit report's issue date is the as-of date for months employed.
  - `assessment/document_rules.py`: `DocumentRuleAssessor.assess_case(facts, findings)`. It never receives documents or identity; the service builds `HouseholdFacts` and the cross-check/unreadable-document findings. It uses `LabellingPolicy.evaluate_all` (every rule judged on its own, so each rule states all its bounds), and the worst finding wins.
  - `enablement/ollama.py`: httpx to `/api/chat` with JSON mode. It raises on any unusable answer, and the service substitutes the fallback.
  - `persistence`: 5 more append-only tables (`application_documents`, `cross_check_results`, `decision_inputs`, `decision_findings`, `enablement_plans`). Uploaded files go to `UPLOAD_DIR/<reference>/`.
- `synthetic/`: the generator (identities, profiles, renderers in `documents/`, inconsistencies, allocation, runs, dataset, seeding, CLI, and `demo.py` for the three hand-built 004 demo profiles). An outer tool layer: it may import `domain`, `labelling`, `ui.client` (seeding goes over HTTP only) and `services.tracing`, never `api`, `persistence`, `assessment` or `services.applications`. `api` and `ui` must not import it.

Conventions that are easy to break:
- Never log Emirates IDs, names or incomes. Add only whitelisted `extra` keys (`services/tracing.py`).
- Money is a `Decimal` internally and a 2-dp string in JSON. Timestamps are UTC ISO strings ending in `Z` (`api/schemas.iso_utc`), because SQLite drops tzinfo.
- A missing reference and a mismatched Emirates ID on lookup must stay indistinguishable (identical 404 body).
- FastAPI 0.161 hides included routers from `app.routes`. Inspect endpoints with `app.openapi()["paths"]` instead.
- Tests use `make_client(assessor=..., **settings)` from `tests/conftest.py`, which gives an in-memory SQLite database and the passcode `test-passcode`. Synthetic cases are in `tests/fixtures/synthetic_applications.py`.
- Generator determinism: each pack uses `pack_rng(seed, index)`; run-level choices (inconsistency slots, outcome targets) use a separate `random.Random(seed)`. Never make one pack depend on another, and never use "today" (documents are dated from `--as-of`, default 2026-10-01). Emirates ID serials come from the pack index (`00NNNNN`), so they need no tracking.
- Labels always come from `policy.evaluate`, never from a sampling target. Generated documents must use only invented organisation names, and every document must show the synthetic marking (Pillow's bundled font has no en dash, so the ID card uses a hyphen).
- Feature 004 conventions:
  - **OCR:** RapidOCR drops spaces in names at the card's native size, so `extraction/emirates_id.py` doubles small images first, and name cross-checks ignore whitespace.
  - **Low OCR confidence** (`OCR_MIN_CONFIDENCE`) makes the ID card unreadable, which routes the case to review.
  - **Never send identity to the LLM.** The profile has no name, ID, employer or exact income (only an income band).
  - **Tests:** `make_client` defaults to `FakeAdvisor` (`tests/conftest.py`), so tests never call Ollama. Upload a demo pack with `tests/fixtures/demo_upload.upload_pack`; the session fixture `demo_packs` writes the three packs once.
  - **File writes:** on Windows, write files from Python scripts with `encoding="utf-8"` (the default cp1252 corrupts en dashes).
- Seeding tests run the 001 app in-process: `ApiClient(base_url="http://testserver", transport=<TestClient>._transport)`. Generator tests write to `tmp_path`, never `data/`; `tests/integration/pack_checks.py` compares documents with answer keys.

## Spec-driven workflow (Spec Kit)

This project is built with GitHub Spec Kit (`specify` CLI 1.2.0, PowerShell scripts). The commands are installed as skills in `.claude/skills/`. The user is learning Spec Kit, so follow the flow rather than writing code ad hoc:

`/speckit-constitution` → per feature: `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-checklist` (optional) → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`

- Project principles live in `.specify/memory/constitution.md`. Every plan must pass its gates.
- Each feature gets a branch and a folder `specs/NNN-feature-name/` (`spec.md`, `plan.md`, `data-model.md`, `contracts/`, `tasks.md`).
- `spec.md` covers *what/why* only. Technology choices belong in `plan.md`.
- Build in thin vertical slices: 001 is a walking skeleton, then synthetic data, extraction, validation, eligibility ML, agent orchestration, chat/enablement, observability.

## Local environment constraints

- Windows, CPU only (no GPU), 15 GB RAM. No Docker, no local Postgres.
- Ollama models: `qwen2.5:7b` (main), `qwen2.5:3b` (fast fallback), `nomic-embed-text` (embeddings). For ID images use RapidOCR (`rapidocr-onnxruntime`, CPU, about 3 s per card, models bundled), not vision LLMs. Tesseract cannot be installed here; EasyOCR (PyTorch) is too heavy.
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
