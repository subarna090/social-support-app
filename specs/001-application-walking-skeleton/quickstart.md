# Quickstart: Application Walking Skeleton

This is a validation guide: it shows how to prove the feature works from end to end. For the API
details see [contracts/api.md](./contracts/api.md), and for the rules see
[data-model.md](./data-model.md).

## Prerequisites

- Windows with `uv` 0.13+ installed. uv downloads Python 3.12 automatically the first time,
  through the `.python-version` file.
- No Ollama, Docker or database server is needed for this slice.

## Setup

```powershell
uv sync                                   # creates .venv with Python 3.12 + deps
Copy-Item .env.example .env               # then set CASEWORKER_PASSCODE in .env
```

The `.env` keys are `DATABASE_URL` (default `sqlite:///./data/app.db`), `CASEWORKER_PASSCODE`,
`ASSESSOR` (default `income_rule`), `RULE_THRESHOLD_AED` (2000), `RULE_BAND_UPPER_AED` (2500),
and `API_BASE_URL` (used by the UI, default `http://127.0.0.1:8000`).

## Automated validation

```powershell
uv run pytest                                  # all tests
uv run pytest tests/unit -q                    # fast: validation + rule boundaries
uv run pytest tests/integration -k lookup      # a single area
uv run ruff check . ; uv run ruff format --check .
```

Expected result: every test passes. The integration suite covers SC-004, SC-005 (at least 20
synthetic cases) and SC-006.

## Run the app (two terminals)

```powershell
uv run uvicorn social_support.api.main:app --reload       # API at http://127.0.0.1:8000/docs
uv run streamlit run src/social_support/ui/app.py         # UI at http://localhost:8501
```

## Manual demo script (SC-007, aim for under 5 minutes)

| # | Action | Expected |
|---|---|---|
| 1 | Submit: family 4, income 6000, a valid ID | **Approve**. The explanation cites 1500.00 per member, the 2000.00 threshold and the rule version. A reference number is shown |
| 2 | Submit: family 2, income 4500 | **Needs Human Review**, reason "borderline income" (2250.00 per member) |
| 3 | Submit: family 1, income 3000 | **Soft Decline** (3000.00 per member) with at least 1 next step |
| 4 | Submit with ID `123-45` and family size 0 | Field messages on both fields; nothing is stored |
| 5 | Submit again with the ID from step 1 | Accepted, with a note that a previous application exists. The outcome follows the rule only |
| 6 | Lookup: reference from step 1 + its ID | The same details and decision as step 1, plus the decision time and rule version |
| 7 | Lookup: reference from step 1 + a different ID | "No application found", the same as an unknown reference |
| 8 | Review list with a wrong passcode | "Access denied", no data |
| 9 | Review list with the correct passcode | Only the step 2 application, newest first |

## Check the audit trail (optional)

Open `data/app.db` in any SQLite viewer:
- Each application has one `decisions` row and `processing_trace_steps` rows in this order:
  RECEIVED → VALIDATED → ASSESSED → STORED → RESULT_RETURNED.
- The JSON logs in the API terminal contain reference numbers but no Emirates IDs or incomes.

## Changing the rule (FR-013)

Set `RULE_THRESHOLD_AED=1800` in `.env` and restart the API. `/api/v1/health` reports a new
`rule_version`, new decisions reference it, and earlier decisions keep their original version.
