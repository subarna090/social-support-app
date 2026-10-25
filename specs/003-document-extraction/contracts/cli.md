# CLI Contract: `social-support-extract`

A new console script (`[project.scripts] social-support-extract =
"social_support.extraction.cli:main"`, also runnable as `python -m social_support.extraction`). It
runs the same extractors as the API, locally, with no API needed. Settings (Ollama URL, model,
threshold) come from the environment or `.env`, as for the API.

Exit codes follow feature 002:

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | the run failed (for example, Ollama unreachable when the resume extractor is required) |
| 2 | invalid arguments or input folder |

Console output never prints names, Emirates IDs or incomes, except from `pack`, which a developer
runs on one fictional pack.

---

## `accuracy`: field-level accuracy report (US4, FR-022–FR-024)

```text
social-support-extract accuracy --run <run folder> [--limit 20] [--out <folder>]
                                [--threshold 0.80] [--quiet]
```

| Option | Default | Meaning |
|---|---|---|
| `--run` | required | a feature 002 run folder (it must contain `run.json` and `packs/`) |
| `--limit` | `20` | number of packs, taken in pack order (FR-022). `0` means all |
| `--out` | `data/reports/extraction/<run-id>-<UTC yyyymmddThhmmss>/` | output folder; refuses to overwrite an existing one |
| `--threshold` | `EXTRACTION_CONFIDENCE_THRESHOLD` | the uncertainty threshold recorded in the report |

Progress goes to stderr, one line per pack (`pack-0007  5/5 read  31.2 s`). At the end the command
prints a summary table of match rate by document type, the output folder and the total time:

```text
Extraction accuracy: s42-n20-…  (20 packs, 9 min 41 s)
  BANK_STATEMENT       99.4%   ( 478/481)
  EMIRATES_ID         100.0%   ( 120/120)
  RESUME               97.8%   ( 312/319)
  ASSETS_LIABILITIES  100.0%   ( 205/205)
  CREDIT_REPORT        99.1%   ( 423/427)
  Text-based docs:  98.9%  (SC-001 target 95%)   ID card: 100.0%  (SC-002 target 90%)
Report: data/reports/extraction/s42-n20-…-20261025T091500/extraction-accuracy.md
```
(The figures are illustrative.)

Errors (exit 2): the run folder is not a generated run; `--limit` is negative; the output folder
exists. A pack whose document fails counts every field of that document as "not found". The
failure is listed in the report rather than stopping the run.

## `pack`: extract one pack and show the result (US1 independent test)

```text
social-support-extract pack <pack folder> [--json]
```

Prints each document's status, method and values with confidence, and marks uncertain values and
values that differ from that pack's answer key. `--json` prints the `DocumentExtraction` list as
JSON. This is meant for fictional generated packs only.

## `broken-samples`: write the demo's broken documents (Clarification, 2026-10-25)

```text
social-support-extract broken-samples --out <folder>
```

Writes the fixed set from research R18 and lists them:
- `truncated.pdf`
- `empty.pdf`
- `spreadsheet-as-id.png` (xlsx bytes)
- `oversized.pdf` (10 MB + 1 byte)
- `no-text.pdf`

It refuses to overwrite existing files (exit 2).

---

## Changed: `social-support-data seed` (FR-025)

```text
social-support-data seed --run <run folder> [--limit N] [--wait-timeout 180]
```

For each pack, the command creates a draft, uploads the five files, waits until every document is
read or failed (at most `--wait-timeout` seconds; a timeout counts the pack as `timed_out` and
moves on), then submits. `seeding_report.csv` gains the columns `extraction_status` (`read`,
`failed:<types>` or `timed_out`) and `routed_by_extraction` (`true`/`false`). The other options
and the exit codes are unchanged.
