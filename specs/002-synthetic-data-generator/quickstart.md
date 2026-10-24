# Quickstart: Synthetic Applicant Data Generator

A validation guide that proves feature 002 works end to end. Formats are in
[contracts/](./contracts/); entities are in [data-model.md](./data-model.md).

## Prerequisites

- `uv sync` has been run (it installs Faker, reportlab, openpyxl and the other dependencies).
- No network access is needed for generation. Seeding (step 7) needs the 001 API running locally.

## 1. Run the tests

```powershell
uv run pytest                  # default suite, including the labelling policy and generator tests
uv run pytest -m slow          # SC-001: 100 packs in under 5 minutes
```

## 2. Generate a small consistent batch (User Story 1)

```powershell
uv run social-support-data generate --count 10 --seed 42
```

Expected: `data/synthetic/s42-n10-<hash>/` with `run.json`, `summary.csv` and 10 folders under
`packs/`, each holding `form.json`, `answer_key.json` and the five documents.

Open `packs/pack-0001/`: the bank statement, resume and credit report open as PDFs, the ID card
opens as an image, and the spreadsheet opens in Excel or LibreOffice. Each one shows the synthetic
marking and agrees with `form.json` on name, Emirates ID, address, employer, income and family
members. No real bank, bureau or government branding appears.

## 3. Reproducibility (FR-006, SC-002)

```powershell
uv run social-support-data generate --count 10 --seed 42                # stops: output already exists (exit 2)
uv run social-support-data generate --count 10 --seed 42 --out data/synthetic-copy
uv run social-support-data generate --count 10 --seed 43
```

Expected: the first command refuses to overwrite. In the copy, every `answer_key.json`, PDF and PNG
is byte-identical to the first run (compare with `Get-FileHash`). Seed 43 gives different packs.

## 4. Inconsistencies (User Story 2)

```powershell
uv run social-support-data generate --count 100 --seed 7 --inconsistency-rate 30 --inconsistency-types income
```

Expected: the summary says `Inconsistencies: 30 (INCOME_MISMATCH 30)`. In `summary.csv`, exactly 30
rows have `inconsistency_count = 1`, and their `expected_routing` is `NEEDS_HUMAN_REVIEW`. For one of
those packs, `form.json` shows a lower income than the salary credits in `bank_statement.pdf`, and
`answer_key.json` records the true and altered values. The `eligibility_outcome` of those packs is
whatever their true facts earn.

## 5. Labelled dataset with an outcome mix (User Story 3)

```powershell
uv run social-support-data generate --count 500 --seed 11 --outcome-mix 40,40,20
```

Expected: `summary.csv` has 500 rows; `eligibility_outcome` counts are exactly 200 / 200 / 100
(the largest-remainder allocation is exact when the percentages divide evenly). The protected
attributes appear only as `audit_nationality` and `audit_gender`.

## 6. Argument errors (edge cases)

```powershell
uv run social-support-data generate --count 0 --seed 1                  # count must be between 1 and 5000
uv run social-support-data generate --count 10 --seed 1 --outcome-mix 50,30,10   # must add up to 100
```

Expected: exit code 2, the one-line message from [contracts/cli.md](./contracts/cli.md), and no
new folder.

## 7. Seed the running application (User Story 4)

```powershell
$env:CASEWORKER_PASSCODE = "demo-passcode"; uv run uvicorn social_support.api.main:app   # terminal 1
uv run social-support-data seed --run data/synthetic/s42-n10-<hash> --limit 10          # terminal 2
```

Expected: `Seeded 10 packs: …`, plus `seeding_report.csv` in the run folder with 10 reference
numbers. Look up one of them in the UI (Look up tab) using the pack's Emirates ID from
`form.json`: the details match the pack. The review queue now lists the seeded applications that
the 001 rule flagged as borderline.

Stop the API and run the seed command again. Expected: the "can't be reached" message, exit code
1, and no packs reported as submitted.

## 8. Privacy checks

- `git status` shows nothing under `data/synthetic/` (it is git-ignored).
- The console output from steps 2–7 contains no names, Emirates IDs or incomes.
- Every `emirates_id` in `summary.csv`'s packs starts its serial with `00` (the reserved block),
  which the integration tests check automatically.
