# Social Support AI Assessor (PoC)

A local-first prototype that automates the assessment of social support applications for a
government social security department. Today the process takes 5–20 working days. The goal is an
explainable recommendation within minutes, with humans kept in the loop for borderline or failed
cases.

> **Synthetic data only.** Never enter real personal information.

**Status:** feature 001 (walking skeleton). An application form leads to a stored, explained
decision, which can be looked up later. Borderline cases go to a caseworker review queue. The
assessment is a placeholder income-per-member rule behind an `Assessor` interface. Later features
replace it with document ingestion, an ML classifier, and LLM agents running on local models
(Ollama).

The project is built spec-first with [GitHub Spec Kit](https://github.com/github/spec-kit). See
[How this project is built](#how-this-project-is-built).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) 0.13 or later. uv downloads Python 3.12 automatically through
  `.python-version`.
- Nothing else for this feature: no Docker, database server or Ollama.

## Setup

```powershell
uv sync                          # creates .venv with Python 3.12 and all dependencies
Copy-Item .env.example .env      # then set CASEWORKER_PASSCODE in .env
```

| Setting | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/app.db` | Any SQLAlchemy URL. A PostgreSQL URL works unchanged |
| `CASEWORKER_PASSCODE` | *(empty)* | Shared passcode for the review queue. When empty, the queue always denies access |
| `ASSESSOR` | `income_rule` | Which `Assessor` implementation to use |
| `RULE_THRESHOLD_AED` / `RULE_BAND_UPPER_AED` | `2000` / `2500` | Rule parameters. Changing them creates a new rule version |
| `API_BASE_URL` | `http://127.0.0.1:8000` | Where the UI finds the API |

## Run

Run the API and the UI in two terminals:

```powershell
uv run uvicorn social_support.api.main:app        # API + docs at http://127.0.0.1:8000/docs
uv run streamlit run src/social_support/ui/app.py # UI at http://localhost:8501
```

The UI has three tabs:
- **Apply**: submit an application and see the recommendation.
- **Look up**: enter a reference number and the matching Emirates ID.
- **Review queue**: caseworkers only; requires the passcode.

## Test

```powershell
uv run pytest                                   # everything (unit, contract, integration, UI)
uv run pytest tests/unit -q                     # fast: validation, rule boundaries, architecture
uv run pytest tests/integration/test_lookup_flow.py::test_mismatched_id_and_unknown_reference_both_return_404
uv run ruff check . ; uv run ruff format --check .
```

## Demo script (about 5 minutes)

| # | Action | Expected |
|---|---|---|
| 1 | Apply: family 4, income 6000 | **Approve**, 1500.00 AED per member, with a reference number |
| 2 | Apply: family 2, income 4500 | **Needs Human Review** (borderline income) |
| 3 | Apply: family 1, income 3000 | **Soft Decline** with suggested next steps |
| 4 | Apply: Emirates ID `123-45`, family 0 | Field-level error messages; nothing is stored |
| 5 | Apply again with the step 1 Emirates ID | Accepted, with a note that a previous application exists |
| 6 | Look up: step 1 reference + its Emirates ID | The same details and decision as step 1 |
| 7 | Look up: step 1 reference + a different ID | "No application found", the same as an unknown reference |
| 8 | Review queue with a wrong passcode | "Access denied." |
| 9 | Review queue with the correct passcode | Only the step 2 application |

The full validation guide, including the audit trail and rule-change checks, is in
[specs/001-application-walking-skeleton/quickstart.md](specs/001-application-walking-skeleton/quickstart.md).

## Architecture

```text
Streamlit UI ──HTTP──▶ FastAPI (api) ──▶ services ──▶ Assessor (domain protocol)
                                            │            └─ IncomePerMemberRuleAssessor (v0.1)
                                            └──▶ persistence (SQLAlchemy) ──▶ SQLite / PostgreSQL
```

- **The UI is a thin client.** It only calls the HTTP API, so later integrations and agents use
  the same contract.
- **`Assessor` is the extension point.** Every implementation must return an explanation and a
  rule version. Assessors receive only family size, income and employment status, never identity.
- **Records are append-only.** Every decision stores its inputs, rule version and a processing
  trace: RECEIVED → VALIDATED → ASSESSED → STORED → RESULT_RETURNED.
- **Privacy:** logs are structured JSON without Emirates IDs or incomes, Streamlit telemetry is
  disabled, and lookups send the ID in the request body, never in the URL.
- **Fails safe:** if assessment fails, the application is still stored and routed to
  Needs Human Review. The system never issues a hard decline automatically.

Architecture tests in `tests/unit/test_architecture.py` enforce these boundaries.

## How this project is built

Every feature goes through Spec Kit's spec-driven loop, using the commands installed in
`.claude/skills/`:

```text
/speckit-constitution → /speckit-specify → /speckit-clarify → /speckit-plan
→ /speckit-tasks → /speckit-analyze → /speckit-implement → /speckit-converge
```

- [`.specify/memory/constitution.md`](.specify/memory/constitution.md): the non-negotiable
  principles (local-first, explainable, human-in-the-loop, fair, test-first, swappable,
  observable, simple).
- [`specs/001-application-walking-skeleton/`](specs/001-application-walking-skeleton/): the
  design record for feature 001: the spec with its clarifications, the plan, research decisions,
  the data model, the API contract, and the tasks.
