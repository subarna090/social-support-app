# Social Support AI Assessor (PoC)

A local-first prototype that automates the assessment of social support applications for a
government social security department. Today the process takes 5–20 working days. The goal is an
explainable recommendation within minutes, with humans kept in the loop for borderline or failed
cases.

> **Synthetic data only.** Never enter real personal information.

**Status:** features 001 (walking skeleton), 002 (synthetic data generator) and 004 (PoC demo).
An applicant fills in the form and uploads five documents: bank statement, Emirates ID card image,
resume, assets and liabilities spreadsheet, and credit report. The system reads them with local,
non-LLM tools (PDF text parsing, RapidOCR for the ID card, spreadsheet reading), cross-checks them
against the form, and recommends **Approve**, **Soft Decline** or **Needs Human Review**, listing
every reason with its value, threshold and source document. A local LLM (Ollama `qwen2.5:7b`) then
writes an economic enablement plan (training, job matches, career counselling) from an anonymised
profile. Review cases go to a passcode-protected caseworker queue. Later features add an ML
classifier, agent orchestration and tracing. See [ROADMAP.md](ROADMAP.md).

The project is built spec-first with [GitHub Spec Kit](https://github.com/github/spec-kit). See
[How this project is built](#how-this-project-is-built).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) 0.13 or later. uv downloads Python 3.12 automatically through
  `.python-version`.
- [Ollama](https://ollama.com) running locally with `qwen2.5:7b` pulled (`ollama pull qwen2.5:7b`)
  for the enablement plan. Without it the app still works and shows a labelled general plan.
- No Docker or database server. RapidOCR's models ship inside its Python wheel (no download).

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
| `API_BASE_URL` | `http://127.0.0.1:8000` | Where the UI finds the API. Read from the environment, then `.env` |
| `UPLOAD_DIR` | `data/uploads` | Uploaded documents, one folder per reference number |
| `DECISION_POLICY` | `decision_v1` | Versioned decision rules in `src/social_support/labelling/policies/` |
| `INCOME_TOLERANCE_PCT` | `10` | Allowed difference between declared and bank statement income |
| `OCR_MIN_CONFIDENCE` | `0.80` | ID card fields read below this confidence send the case to review |
| `OLLAMA_URL` / `ENABLEMENT_MODEL` | `http://localhost:11434` / `qwen2.5:7b` | Local LLM for enablement (`qwen2.5:3b` is faster) |
| `ENABLEMENT_TIMEOUT_S` | `90` | After this, the labelled fallback plan is shown |

## Run

Run the API and the UI in two terminals:

```powershell
uv run uvicorn social_support.api.main:app        # API + docs at http://127.0.0.1:8000/docs
uv run streamlit run src/social_support/ui/app.py # UI at http://localhost:8501
```

The UI has three tabs:
- **Apply**: fill in the form, attach the five documents, and see the recommendation, its reasons,
  the cross-document checks, the values read from each document and the enablement plan.
- **Look up**: enter a reference number and the matching Emirates ID.
- **Review queue**: caseworkers only; requires the passcode.

## Test

```powershell
uv run pytest                                   # everything except slow tests (about 3 minutes, real OCR)
uv run pytest -m slow                           # 200-pack volume checks and the 100-pack timing test
uv run pytest tests/unit -q                     # fast: validation, rule boundaries, architecture
uv run pytest tests/integration/test_lookup_flow.py::test_mismatched_id_and_unknown_reference_both_return_404
uv run ruff check . ; uv run ruff format --check .
```

## Demo script (about 10 minutes)

**Before the audience arrives:**

```powershell
ollama list                                          # qwen2.5:7b must be listed
uv run social-support-data demo                      # writes data/demo/{approve,soft_decline,review}
uv run uvicorn social_support.api.main:app           # terminal 1
uv run streamlit run src/social_support/ui/app.py    # terminal 2
```

Each `data/demo/<case>/form.json` holds the values to type into the form (its `submission` block);
the five files in the same folder are the uploads. Submitting one application before the audience
arrives loads the OCR engine and the LLM, so the live runs are faster.

| # | Action | Expected |
|---|---|---|
| 1 | Apply with `data/demo/approve` (Mariam, family 5, income 6000, Employed) | **Approve** in a few seconds. Four green reasons: income per member 1200.00 below 2000.00, net wealth 30000.00 within 500000.00, credit score 720 with no defaults, 22 of the last 24 months worked. All four cross-checks pass, and the values read from each document are listed |
| 2 | Wait under the decision | Enablement plan (training, job matches, counselling) built on the resume's retail and customer-service skills, labelled with the model name (about 20-45 s on CPU) |
| 3 | Apply with `data/demo/soft_decline` (Omar, family 2, income 18000) | **Soft Decline**: income per member 9000.00 above 2500.00 and net wealth 650000.00 above 500000.00, with next steps |
| 4 | Apply with `data/demo/review` (Hassan, family 4, **declared income 7000**) | **Needs Human Review**: income per member 2250.00 is in the borderline band, and the declared 7000.00 differs from the bank statement's 9000.00 by more than 10% |
| 5 | Review queue tab, passcode from `.env` | The Hassan case, with both reasons |
| 6 | Apply with the approve values but attach the resume PDF as the ID card | **Needs Human Review**: the Emirates ID card could not be read |
| 7 | Look up step 1's reference with Mariam's Emirates ID | The same decision and reasons |

The full validation guide is in [specs/004-poc-demo/quickstart.md](specs/004-poc-demo/quickstart.md).
The 001 form-only endpoint (`POST /api/v1/applications`) still exists for the generator's `seed`
command; the UI always requires the documents.

## Synthetic data

Feature 002 generates fictional applicant packs for tests, demos and model training. Each pack has
the application form details, five documents (bank statement, resume and credit report as PDFs, an
ID card image, an assets and liabilities spreadsheet) and an answer key with the true values.

```powershell
uv run social-support-data demo                                           # the three fixed demo applicants
uv run social-support-data generate --count 10 --seed 42                  # consistent packs
uv run social-support-data generate --count 100 --seed 7 --inconsistency-rate 30 --inconsistency-types income
uv run social-support-data generate --count 500 --seed 11 --outcome-mix 40,40,20   # training set
uv run social-support-data seed --run data/synthetic/<run-id> --limit 10   # submit to the running API
```

- **Output:** `data/synthetic/<run-id>/` with `run.json`, `summary.csv` (one row per pack) and
  `packs/pack-NNNN/`. The same count, seed and settings always give the same files; an existing
  run is only replaced with `--overwrite`.
- **Two labels per pack:** the *eligibility outcome* comes from the household's true facts through
  the versioned labelling policy (`src/social_support/labelling/policies/eligibility_v1.toml`, an
  ordered list of rules where the first match wins). The *expected routing* is Needs Human Review
  when an inconsistency was injected, otherwise the eligibility outcome.
- **Inconsistencies:** `income`, `address`, `family_size`, `identity`, `employment`. At most one
  per pack, recorded in its answer key with the true and the altered value.
- **Privacy:** everything is fictional. Documents carry a "SYNTHETIC – NOT A REAL DOCUMENT" marking,
  organisations are invented, emails use `example.com`, and Emirates ID serials start with `00`
  (a reserved block). Output is git-ignored. Nationality and gender appear in `summary.csv` only as
  `audit_` columns, for fairness evaluation, never as model inputs.

Formats: [specs/002-synthetic-data-generator/contracts/](specs/002-synthetic-data-generator/contracts/).
Validation guide: [specs/002-synthetic-data-generator/quickstart.md](specs/002-synthetic-data-generator/quickstart.md).

## Architecture

```text
Streamlit UI ──HTTP──▶ FastAPI (api) ──▶ services ─┬─▶ extraction (pypdf, RapidOCR, openpyxl)
                                                   ├─▶ domain cross-checks (form vs documents)
                                                   ├─▶ DocumentRuleAssessor ─▶ decision_v1.toml
                                                   ├─▶ enablement (Ollama qwen2.5 over HTTP)
                                                   └─▶ persistence (SQLAlchemy) ─▶ SQLite / PostgreSQL
                                                                   + uploaded files on disk
```

Feature 004 flow for one application: RECEIVED → VALIDATED → EXTRACTED → CROSS_CHECKED → ASSESSED
→ STORED → RESULT_RETURNED, then ENABLEMENT when the UI asks for the plan.

- **Every rule is checked and reported.** Each matching rule in `decision_v1.toml` is a finding;
  the most severe one decides (Needs Human Review > Soft Decline > Approve). Failed cross-checks and
  unreadable documents are review findings.
- **The document assessor never sees identity.** It receives only household facts (no names, IDs
  or protected attributes) plus findings the service has already built.
- **The LLM is optional and anonymised.** It gets skills, education, experience, last job title,
  employment status, family size, outcome and an income band, never the name, ID, employer or
  exact income. If it is slow or down, a labelled fallback plan is shown and the decision is
  unchanged. The exact profile sent, the plan and the latency are stored.

- **The UI is a thin client.** It only calls the HTTP API, so later integrations and agents use
  the same contract.
- **`Assessor` is the extension point.** Every implementation must return an explanation and a
  rule version. Assessors receive only family size, income and employment status, never identity.
- **Records are append-only.** Every decision stores its inputs (documents with their SHA-256,
  extracted values with OCR confidence and timings, cross-checks, the facts used), its findings,
  its rule version and a processing trace.
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
- [`specs/004-poc-demo/`](specs/004-poc-demo/): the condensed design record for the demo slice
  (documents to decision and enablement).
