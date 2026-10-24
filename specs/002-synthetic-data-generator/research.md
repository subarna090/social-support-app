# Research: Synthetic Applicant Data Generator

Decisions for feature 002. Each one records what was chosen, why, and what was rejected. The user
fixed the libraries (Faker, reportlab, Pillow, openpyxl, pandas), the location of the labelling
policy (versioned data plus its own evaluator module) and the default output folder
(`data/synthetic/<run-id>/`).

---

## R1. Package layout and layering

**Decision**: two new subpackages.

- `social_support/labelling/`: pure and reusable. It holds `HouseholdFacts`, the policy loader,
  the evaluator, and the policy files (`policies/eligibility_v1.toml`). It imports only
  `social_support.domain` and the standard library.
- `social_support/synthetic/`: the generator, the document renderers, inconsistency injection,
  dataset export, seeding, and the CLI. It may import `domain`, `labelling`, `ui.client` (the
  existing HTTP client, for seeding) and `services.tracing` (logging only). It must not import
  `api`, `services.applications`, `persistence` or `assessment`.

Architecture tests in `tests/unit/test_architecture.py` enforce both rules.

**Rationale**: feature 005 (ML) needs the policy and `HouseholdFacts` without pulling in reportlab
or Faker, so `labelling` is kept free of them. Seeding through `ui.client` means the generator
reaches the application only over HTTP, the same way the UI does (FR-021: "existing submission
path only").

**Alternatives considered**: putting the policy in `domain/`. Rejected, because `domain/` holds
the application's own types, while the policy is a data-generation concern that feature 005 will
also reuse. A separate top-level project for the generator was rejected as well: it would mean
two dependency sets for no benefit (Principle VIII).

## R2. Labelling policy format and versioning

**Decision**: a TOML file per policy version, read with the standard-library `tomllib`. The file
holds an ordered `[[rules]]` array; each rule has an `id`, an `outcome`, `conditions` (a list of
`{factor, op, value}`, all of which must hold), and a `reason` template. The last rule must have
no conditions; it is the default. The version id is
`eligibility/v1+<hash>`, where `<hash>` is the first 8 hex chars of the SHA-256 of the file text
with line endings normalised to `\n`, following the 001 rule-version style. Normalising line endings keeps the id stable when git converts to CRLF on
Windows. Format:
[contracts/labelling-policy.md](./contracts/labelling-policy.md).

**Rationale**: the policy is data a reviewer can read and change without touching code (Principle
VI: configuration not hard-coded). Hashing the file means any edit, even a threshold, produces a
new version id, so labels stay traceable (FR-015). TOML needs no new dependency and allows
comments next to each rule explaining it.

**Alternatives considered**: a Python module of rule functions (not reviewable as data and harder
to version); YAML (needs PyYAML); JSON (no comments).

## R3. Rules in eligibility policy v1

**Decision**: the following eight rules, evaluated in order. Thresholds for income per member
match the 001 rule (2000 / 2500 AED) so the two stay comparable.

| # | Rule id | Conditions (all must hold) | Outcome |
|---|---|---|---|
| 1 | `high_net_wealth` | `net_wealth_aed > 500000` | SOFT_DECLINE |
| 2 | `income_above_band` | `income_per_member_aed > 2500` | SOFT_DECLINE |
| 3 | `active_credit_defaults` | `active_credit_defaults >= 1` | NEEDS_HUMAN_REVIEW |
| 4 | `poor_credit_score` | `credit_score < 550` | NEEDS_HUMAN_REVIEW |
| 5 | `borderline_income` | `income_per_member_aed >= 2000` | NEEDS_HUMAN_REVIEW |
| 6 | `low_income_not_in_work` | `employment_status in [UNEMPLOYED, STUDENT, RETIRED]` | APPROVE |
| 7 | `low_income_stable_work` | `months_employed_last_24 >= 12` | APPROVE |
| 8 | `unstable_work_history` | *(default)* | NEEDS_HUMAN_REVIEW |

Because rules are evaluated in order, later rules inherit the negation of earlier ones: rule 6
only sees households with income per member below 2000, no defaults and a score of 550 or more.
The policy file says this in a comment at the top, and the boundary tests cover it.

**Rationale**: a decision list is fully explainable (each label names one rule and the values it
compared), easy to test at each boundary, and produces axis-aligned, step-shaped decision
boundaries, which gives feature 005 a concrete, data-based reason for choosing a tree-based
classifier. No rule uses a protected attribute (FR-012).

**Alternatives considered**: a weighted points score (rejected by the user in clarify Q1); adding a
rule for family size alone (family size already enters through income per member).

## R4. Meeting the outcome mix

**Decision**:

1. Turn the requested mix into exact per-outcome counts with the largest-remainder method, so
   rounding never moves an outcome by more than one pack (edge case).
2. Give each pack slot a target eligibility outcome, then shuffle the slots with the run's random
   generator.
3. For each slot, sample a household profile from priors tuned to the target outcome, then label
   it with the policy, retrying until the label matches (rejection sampling, at most 200 attempts
   per pack, then stop with an error naming the outcome).
4. When no mix is requested, sample from the untuned base priors and label whatever results.

The label always comes from the policy; the generator never writes an outcome directly.

**Rationale**: this guarantees SC-005 and the labelling-correctness checks, because every label is
recomputed by the same evaluator the tests use. Tuned priors keep rejection rare (target: under 5
attempts on average).

**Alternatives considered**: generating random profiles and dropping surplus ones (wasteful, and
the final count is not exact); assigning labels and then building matching profiles by hand-coded
inverse logic (duplicates the policy in code, and breaks silently when the policy changes).

## R5. Reproducibility

**Decision**:

- There is one master `random.Random(seed)`. Each pack gets its own sub-seed, `seed * 1_000_003 +
  index`, used for its own `random.Random` and `Faker.seed_instance`, so pack *i* is the same
  whatever else is in the batch.
- The *as-of* date that every document date is computed from defaults to the fixed date
  `2026-10-01` and can be changed with `--as-of`. It is never "today".
- Renderers are made deterministic: reportlab with `invariant=1`, which removes timestamps and
  random document ids; Pillow PNG with no metadata; openpyxl workbook properties set to the as-of
  date.
- "Identical content" (FR-006, SC-002) is defined as: `form.json`, `answer_key.json`,
  `summary.csv`, PDFs and PNGs are byte-identical; `.xlsx` files have identical cell values (zip
  entries carry write-time timestamps); `run.json` is identical apart from `generated_at`.

**Rationale**: a fixed as-of date is the only way the same seed gives the same statements next
month. Per-pack sub-seeds make a failing pack easy to regenerate on its own.

**Alternatives considered**: a single global random stream (pack contents depend on the order of
earlier packs); post-processing xlsx zips to fix timestamps (extra code for a file that
consumers read by value).

## R6. Synthetic identities, the reserved ID block, and contact details

**Decision**:

- Names come from two sources: Faker with the locales `en_GB`, `en_IN` and `en_PH`, plus a small
  curated list of Arabic given names and family names, written in English letters, kept in
  `synthetic/data/names.toml` (Faker's Arabic locales produce Arabic script). Together they give a
  realistic UAE resident mix in English text.
- Emirates ID numbers: `784-YYYY-NNNNNNN-C`, where `YYYY` is the birth year, the 7-digit serial is
  `00` followed by the pack index zero-padded to 5 digits (pack 1 gets `0000001`, pack 5000 gets
  `0005000`), and `C` is a Luhn check digit over the first 14 digits. Every number therefore passes
  the 001 format check and a Luhn check, and can be recognised as synthetic by its serial prefix
  (FR-016).

  Deriving the serial from the pack index makes numbers unique within a run *without* tracking
  which numbers are used. Tracking would make pack *i* depend on the packs generated before it,
  which breaks R5, and drawing at random per pack would very probably collide at 5,000 packs. The
  only exception is an `IDENTITY_MISMATCH`, whose altered serial digit may coincide with another
  pack's number. That is acceptable, because it is recorded as the altered value.
- Email addresses use the reserved domain `example.com` (RFC 2606). Phone numbers use the pattern
  `+971 50 000 NNNN`.
- Addresses are built from real emirate names plus fictional district and street names from
  `names.toml` (for example "Villa 12, Street 7, Al Waha District, Sharjah").
- Employers, banks and the credit bureau are fictional and clearly invented: "Desert Falcon Demo
  Bank", "Demo Credit Information Bureau", employers like "Oasis Logistics (Demo) LLC".

**Rationale**: reserved domains and an ID block make synthetic data recognisable at a glance and
easy to scan for (SC-006). Coincidental matches between generated names and real people are
unavoidable and harmless, because they are never combined with a real ID, address or employer.

**Alternatives considered**: Faker's `ar_AE` locale (Arabic script, but documents are English per
the spec's assumptions); random IDs without a reserved block (impossible to tell apart from real
ones).

## R7. Document rendering

**Decision**:

| Document | Format | How |
|---|---|---|
| Bank statement | PDF, text-based | reportlab platypus: header, account summary, a transaction table for 3–6 months (salary or other income credits, rent, utilities, groceries, loan repayments), closing balance per month |
| Emirates ID card | PNG, 1012×638 px (ID-1 card ratio) | Pillow: plain layout titled "MOCK RESIDENT IDENTITY CARD", a grey silhouette instead of a photo, name, ID number, nationality, date of birth, sex, expiry; red "SYNTHETIC" banner |
| Resume | PDF, text-based | reportlab: contact block, summary, employment history (employer, title, start and end month), education, skills |
| Assets and liabilities | XLSX | openpyxl: sheets `Assets` (type, description, value), `Liabilities` (type, lender, outstanding balance, monthly payment) and `Summary` (totals and net wealth as plain values, not formulas) |
| Credit report | PDF, text-based | reportlab: fictional bureau header, subject details including the address on file, a "Household members on file" table (name, relationship, age), credit score (300–900), open accounts table, number of active defaults |

Every page and the ID image carry a diagonal or banner "SYNTHETIC – NOT A REAL DOCUMENT" marking
(FR-017). No logos, emblems, coats of arms or real organisation names are used.

Fonts: reportlab's built-in Helvetica; Pillow's bundled default font at a chosen size
(`ImageFont.load_default(size=…)`), so output never depends on fonts installed on the machine.

Totals in the spreadsheet are stored as values because openpyxl writes formulas without cached
results, and a reader would see empty cells.

**Rationale**: text-based PDFs let feature 003 test text extraction, and the ID card image gives
it an OCR case, which covers text, image and tabular data (the brief's multimodal requirement).
Scan effects (blur, rotation, noise) stay out of scope, as the spec's assumptions allow.

**Alternatives considered**: HTML-to-PDF conversion (needs a browser engine or wkhtmltopdf);
rendering every document as an image (removes the text-extraction case).

## R8. Inconsistency injection

**Decision**: at most one injected inconsistency per pack. Exact counts come from
`rate × count` rounded half up with `Decimal` (5 packs at 50% gives 3; Python's `round` would give
2); the packs and their types are chosen up front with the run's random
generator, from the requested types. Each type states where the altered value goes and when it
applies:

| Type | Altered location | Applies when |
|---|---|---|
| `INCOME_MISMATCH` | form's net monthly income, under-reported by 20–40% | true income > 0 |
| `ADDRESS_MISMATCH` | credit report's address on file (a different, plausible address) | always |
| `FAMILY_SIZE_MISMATCH` | form's family size and member list: one fictional member added, or one removed (never below 1), so the form agrees with itself but not with the credit report's household members | always (removal only when the household has members) |
| `IDENTITY_MISMATCH` | ID card: either a misspelt name or one changed serial digit (Luhn recomputed) | always |
| `EMPLOYMENT_MISMATCH` | resume's current employer differs from the form's employer | employment status is EMPLOYED or SELF_EMPLOYED |

A slot assigned a type that needs income or employment passes that need to the profile sampler
(R4) as an extra constraint, so the requested count is always met exactly.

**Rationale**: the altered side follows real patterns: applicants under-report income on the form,
credit bureaus hold stale addresses, ID data gets mistyped. One inconsistency per pack keeps the
answer key and validation scoring simple; several per pack can come later if feature 004 needs
them.

**Alternatives considered**: several inconsistencies per pack (harder to score, no current need);
always altering the form (makes every mismatch "the applicant lied", which is unrealistic for
addresses).

## R9. Output layout, run id and overwrite protection

**Decision**: the default root is `data/synthetic/`, already git-ignored by the existing `data/`
rule. The run id is deterministic: `s<seed>-n<count>-<settings hash[:6]>`. If the run folder exists,
generation stops before writing anything unless `--overwrite` is given, in which case the folder
is deleted and rebuilt. Writes go to a temporary sibling folder that is renamed when complete, so
an interrupted run never leaves a half-written folder under the real name. Layout:
[contracts/pack-format.md](./contracts/pack-format.md).

**Rationale**: a deterministic run id makes "same request, same folder" natural and turns the
"never silently mix old and new packs" edge case into a simple existence check.

**Alternatives considered**: timestamped run ids (every rerun gets a new folder, so reruns cannot be
compared by path, and old runs pile up).

## R10. Summary table and protected attributes

**Decision**: `summary.csv`, written with pandas, one row per pack. It holds the labelling factors,
the label columns and inconsistency columns. Nationality and gender appear only as `audit_`
columns (`audit_nationality`, `audit_gender`), documented as not for use as model inputs. Column
reference: [contracts/pack-format.md](./contracts/pack-format.md#summarycsv).

**Rationale**: Constitution IV requires the eligibility model's evaluation report to show outcome
rates across groups, so feature 005 needs the attributes for evaluation, not for training. A fixed
`audit_` prefix lets feature 005 drop them with one rule, and lets a test assert that the
labelling facts never include them.

**Alternatives considered**: leaving the attributes out entirely (makes the fairness report
impossible); a separate audit file (two files to keep aligned for no gain).

## R11. Seeding the running application

**Decision**: the `seed` command reads `form.json` from each pack of a run and posts its
`submission` block through `social_support.ui.client.ApiClient`. That client already honours
`API_BASE_URL` from the environment or `.env` (feature 001, T051). The command writes
`seeding_report.csv` into the run folder. On the first connection failure it stops, prints a clear
message, and writes the report containing only the packs that were actually submitted (FR-020). A
422 from the API is recorded for that pack as `rejected` and seeding continues. Console output
shows pack ids, reference numbers and counts only, never names, IDs or incomes.

Tests run seeding against the real 001 app in-process by passing a transport that routes requests
to a FastAPI `TestClient`, so no server is needed.

**Rationale**: reusing the one HTTP client keeps the configuration (`API_BASE_URL`) and error
handling identical to the UI's.

**Alternatives considered**: calling `ApplicationService` directly (bypasses the submission path,
violating FR-021); a new HTTP client (duplicate code and configuration).

## R12. CLI

**Decision**: one console script `social-support-data` with subcommands `generate` and `seed`,
built with the standard-library `argparse` and registered in `[project.scripts]`. It also runs as
`python -m social_support.synthetic`. All argument checks (count 1–5000, rate 0–100, mix adding up
to 100, existing run folder) happen before anything is written. Invalid arguments exit with code 2
and a one-line message. Contract: [contracts/cli.md](./contracts/cli.md).

**Rationale**: argparse needs no dependency, and two subcommands is a small surface.

**Alternatives considered**: Typer or Click (a new dependency for two subcommands).

## R13. Dependencies

**Decision**:

- Runtime: `faker`, `reportlab`, `openpyxl` are new; `pillow` and `pandas` are already installed
  through Streamlit but become direct dependencies, because the generator imports them.
- Dev: `pypdf`, used only by tests to read PDF text back and check it against the answer key.

All are pure Python or ship Windows wheels and need no system packages, and none needs a network
connection at run time.

## R14. Testing approach

**Decision**:

- **Test-first** for the labelling evaluator and policy v1 (Principle V: this is decision logic):
  every rule boundary, first-match order, the default rule, invalid policy files (unknown factor or
  operator, missing default rule, default rule not last), and version-id stability.
- **Unit**: the Emirates ID generator (format, Luhn, reserved block, accepted by
  `domain.validation`), largest-remainder allocation, inconsistency selection and applicability,
  and the sampler meeting a mix over 500 sampled profiles with no rendering (SC-005).
- **Integration**: generate a small batch into `tmp_path`, then check every cross-document value
  against the answer key by reading the PDFs back with pypdf, the xlsx with openpyxl and the form
  JSON (SC-003, SC-004); check the synthetic marking on every document (SC-006); check determinism
  across two runs (SC-002); check CLI argument errors write nothing.
- **End to end** (Principle V): generate 20 packs, seed them into the 001 app in-process, then look
  up 3 of them (User Story 4).
- **Performance and volume** (SC-001: 100 packs in under 5 minutes; SC-003 and SC-004: checks over
  at least 200 packs): tests marked `slow`, excluded from the default run with
  `addopts = "-m 'not slow'"` and run with `uv run pytest -m slow`. The default suite checks the same
  properties on 10–40 packs and stays fast.
- **Document checks**: answer keys hold canonical values (money `"6000.00"`, dates `YYYY-MM-DD`).
  The checker formats them with the renderers' own `money()` and `month_label()` helpers before
  searching PDF text or xlsx cells. For the ID card PNG, the renderer also returns, for tests only,
  the box each field was drawn in; tests confirm that each box contains drawn text, and that an
  identity mismatch changes the drawn card. The boxes are not written to the answer key (clarify
  Q3: values only).
