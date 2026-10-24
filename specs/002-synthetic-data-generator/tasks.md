---

description: "Task list for feature 002: Synthetic Applicant Data Generator"
---

# Tasks: Synthetic Applicant Data Generator

**Input**: Design documents from `/specs/002-synthetic-data-generator/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: included. Constitution Principle V requires the labelling policy (decision logic) to be
built test-first, plus an end-to-end test over synthetic data, and SC-002 to SC-006 are verified by
automated checks. Test tasks come before their implementation tasks and MUST fail before the
implementation is written.

**Organization**: Tasks are grouped by user story so that each story can be implemented and
tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 / US2 / US3 / US4, matching the user stories in spec.md
- Paths are relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependencies, entry point, package skeleton

- [ ] T001 Update `pyproject.toml` (research R12, R13, R14):
  - Add runtime dependencies with `uv add faker reportlab openpyxl pillow pandas`, and the dev
    dependency with `uv add --dev pypdf`.
  - Add `[project.scripts] social-support-data = "social_support.synthetic.cli:main"`.
  - In `[tool.pytest.ini_options]`, add `markers = ["slow: long-running timing tests (SC-001)"]` and
    `addopts = "-m 'not slow'"`.
  - Run `uv sync` and confirm that `uv run python -c "import faker, reportlab, openpyxl, PIL, pandas, pypdf"` succeeds.
- [ ] T002 Create the package skeleton from plan.md:
  - `src/social_support/labelling/{__init__.py,facts.py,policy.py}` and
    `src/social_support/labelling/policies/`.
  - `src/social_support/synthetic/{__init__.py,__main__.py}`, `src/social_support/synthetic/documents/__init__.py`,
    `src/social_support/synthetic/data/`.
  - `tests/e2e/__init__.py`.
  - `synthetic/__init__.py` defines `GENERATOR_VERSION = "0.1.0"`. `__main__.py` calls `cli.main()`.
- [ ] T003 Confirm that `.gitignore` already ignores `data/`, so `data/synthetic/` is ignored
  (FR-018). Run `git check-ignore data/synthetic/x` and expect a match; add `data/` only if it is
  missing.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the labelling policy, the household facts and profile, and synthetic identities. Every
story depends on these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Labelling policy (test-first, Principle V)

- [ ] T004 [P] Write `tests/unit/test_labelling_policy.py` against
  [contracts/labelling-policy.md](./contracts/labelling-policy.md) and research R3. Confirm it
  fails. It covers:
  - **One boundary pair per rule**, each with otherwise neutral facts:
    - `net_wealth_aed` 500000.00 gives no SOFT_DECLINE from rule 1; 500000.01 gives SOFT_DECLINE
      (`high_net_wealth`).
    - `income_per_member_aed` 2500.00 versus 2500.01 (`income_above_band`).
    - `active_credit_defaults` 0 versus 1 (`active_credit_defaults`).
    - `credit_score` 550 versus 549 (`poor_credit_score`).
    - `income_per_member_aed` 1999.99 versus 2000.00 (`borderline_income`).
    - Each of UNEMPLOYED, STUDENT and RETIRED versus EMPLOYED (`low_income_not_in_work`).
    - `months_employed_last_24` 11 versus 12 (`low_income_stable_work`).
    - The default rule `unstable_work_history`.
  - **First match wins**: high net wealth combined with low income gives SOFT_DECLINE from
    `high_net_wealth`.
  - **`LabelResult`**: `compared` holds exactly the matching rule's factors, and `reason` renders
    money with 2 decimal places.
  - **Version id**: matches `eligibility/v1+[0-9a-f]{8}`, is stable across loads, and is the same
    for LF and CRLF copies of the file written to `tmp_path`.
  - **Invalid files** written to `tmp_path`: each `PolicyError` message from the contract table (no
    rules, duplicate id, unknown outcome, unknown factor, unknown operator, default rule not last or
    missing, unknown placeholder).
- [ ] T005 [P] Implement `HouseholdFacts` in `src/social_support/labelling/facts.py` (data-model
  HouseholdFacts). It is a frozen dataclass with exactly these fields: `family_size` (int ≥ 1),
  `net_monthly_income_aed` (Decimal ≥ 0), `income_per_member_aed` (Decimal, 2 dp),
  `employment_status` (`domain.models.EmploymentStatus`), `months_employed_last_24` (int 0–24),
  `total_assets_aed` (Decimal ≥ 0), `total_liabilities_aed` (Decimal ≥ 0), `net_wealth_aed`
  (Decimal), `credit_score` (int 300–900) and `active_credit_defaults` (int ≥ 0). `__post_init__`
  raises `ValueError` on out-of-range values. Add a `HouseholdFacts.build(...)` classmethod that
  derives `income_per_member_aed` (ROUND_HALF_UP to 2 dp) and `net_wealth_aed`.
- [ ] T006 Implement `src/social_support/labelling/policy.py`:
  - `PolicyError`, `Condition`, `Rule`, `LabellingPolicy`, `LabelResult` (data-model) and
    `load_policy(name="eligibility", version="v1", path=None)`.
  - Read the file with `tomllib`, from package data through `importlib.resources` unless a `path`
    is given.
  - Run every validation from the contract table.
  - The version id hashes the file text with line endings normalised to `\n`.
  - `LabellingPolicy.evaluate(facts)` applies first-match-wins with `Decimal` comparisons and
    renders the reason with money at 2 dp.
  - Export `load_policy`, `HouseholdFacts`, `LabelResult` and `PolicyError` from
    `labelling/__init__.py`.
  - Depends on T005.
- [ ] T007 Create `src/social_support/labelling/policies/eligibility_v1.toml` with the 8 ordered
  rules, ids, outcomes, conditions and reason templates from research R3. Add a header comment
  explaining first-match-wins and that later rules inherit the negation of earlier ones. T004 then
  passes.

### Architecture guards

- [ ] T008 Extend `tests/unit/test_architecture.py` (research R1, Constitution IV):
  - `labelling` may import only `social_support.domain` and the standard library. Assert that it
    imports none of `faker`, `reportlab`, `PIL`, `openpyxl`, `pandas`, `httpx`, `sqlalchemy`,
    `fastapi`, `streamlit`, or `social_support.{persistence,services,api,ui,assessment,synthetic}`.
  - `synthetic` must not import `social_support.{api,persistence,assessment}` or
    `social_support.services.applications`.
  - `api` and `ui` must not import `social_support.synthetic` (FR-021: no new screen or endpoint).
  - The exact `HouseholdFacts` field set equals the 10 names in T005, and contains none of
    `nationality`, `gender`, `religion`, `ethnicity`, `marital_status`, `full_name` or
    `emirates_id`.
  - Mutation-check each guard once by planting a forbidden import, then remove it.

### Identities and household profile

- [ ] T009 [P] Write `tests/unit/test_identities.py` (research R6, FR-016) and confirm it fails. It
  covers:
  - `emirates_id(birth_year, pack_index)` returns `784-YYYY-00NNNNN-C`, where `YYYY` is the birth
    year and `NNNNN` is the pack index zero-padded (pack 1 gives `784-1990-0000001-0`).
  - The check digit is a valid Luhn digit over the first 14 digits.
  - Every ID is accepted by `social_support.domain.validation.validate_emirates_id`.
  - Pack indexes 1–5000 give 5,000 distinct IDs, and a pack's ID does not depend on any other pack
    (generating pack 7 alone gives the same ID as in a full batch).
  - Emails end with `@example.com`; phones match `+971 50 000 NNNN`.
  - Addresses use a district from `names.toml`.
  - The same seed gives the same identities.
- [ ] T010 [P] Create `src/social_support/synthetic/data/names.toml`, all fictional:
  - Curated Arabic given and family names written in English letters (at least 30 of each).
  - Fictional districts (at least 15) and street patterns, plus the 7 emirate names.
  - Fictional employers (at least 25, each with "(Demo)" in the name), bank name
    `Desert Falcon Demo Bank`, bureau name `Demo Credit Information Bureau`.
  - Universities and job titles.
- [ ] T011 Implement `src/social_support/synthetic/identities.py` (research R6) and make T009 pass.
  - `IdentityFactory(rng, faker_locales=("en_GB","en_IN","en_PH"))` mixes Faker names with the
    curated list.
  - `emirates_id(birth_year, pack_index)` builds the serial as `00` plus the pack index padded to 5
    digits, adds the Luhn check digit and formats as `784-YYYY-NNNNNNN-C` (research R6). It is
    stateless, so there is no "used numbers" tracking.
  - Also provides `address()`, `email(name)`, `phone()` and `employer()`.
  - Depends on T010.
- [ ] T012 [P] Write the profile part of `tests/unit/test_profile_sampler.py` (data-model
  HouseholdProfile invariants) and confirm it fails. It covers:
  - `family_size == 1 + len(members)`.
  - `active_credit_defaults` equals the number of DEFAULT accounts.
  - EMPLOYED or SELF_EMPLOYED means a current job; other statuses mean none.
  - A SALARY payer equals the current employer.
  - `to_facts(profile, as_of)` computes `months_employed_last_24` from the job months in the 24
    months before `as_of` (overlapping jobs counted once), and the net income sums all sources.
  - Natural sampling with the same per-pack seed gives an identical profile.
  - Spec edge cases are reachable: over 500 naturally sampled profiles there is at least one with
    family size 1, one with family size 10 or more, one with zero income, and one whose income is
    only from non-salary sources.
- [ ] T013 Implement `src/social_support/synthetic/profile.py` and make T012 pass.
  - The `HouseholdProfile` dataclasses (identity, contact, members, jobs, income sources, assets,
    liabilities, credit accounts) as in data-model.
  - `sample_profile(rng, identities, as_of)` uses base priors: family size 1–10 (10 or more
    supported), all 5 employment statuses, zero and non-salary income cases included (spec edge
    cases).
  - `to_facts(profile, as_of) -> HouseholdFacts`.
  - Per-pack seeding: `pack_rng(seed, index) = random.Random(seed * 1_000_003 + index)` (research
    R5).
  - Depends on T005 and T011.

**Checkpoint**: `uv run pytest tests/unit` is green. The policy can label any sampled profile.

---

## Phase 3: User Story 1 - Generate a reproducible batch of consistent applicant packs (Priority: P1) 🎯 MVP

**Goal**: `social-support-data generate --count N --seed S` writes N packs, each with `form.json`,
`answer_key.json` and five readable, synthetic-marked documents that agree with each other,
reproducibly.

**Independent Test**: generate 10 packs, open one pack's documents and compare them with
`form.json` and `answer_key.json`; regenerate with the same seed into another folder and compare.

### Tests for User Story 1 (write first, confirm they fail)

- [ ] T014 [P] [US1] Write `tests/integration/test_generate_batch.py` (FR-001–FR-005, FR-016,
  FR-017, SC-003, SC-006). Call `run.generate(GenerationRequest(count=10, seed=42, output_root=tmp_path))`
  and assert:
  - The layout from [contracts/pack-format.md](./contracts/pack-format.md) exists: `run.json`, and
    `packs/pack-0001`…`pack-0010` each with 7 files.
  - `form.json["submission"]` passes the 001 request schema (`api.schemas.SubmitApplicationRequest`
    validates it).
  - For every pack, each value in `answer_key.documents.<type>` appears where it should: in the
    PDF text extracted with pypdf (bank statement, resume, credit report), in the xlsx cells (totals
    and net wealth on `Summary`), and in `form.json`. Answer-key values are canonical (`"6000.00"`,
    `YYYY-MM-DD`); format them with `documents.common.money()` and `month_label()` before searching
    document text. Every shared field (name, Emirates ID, date of birth, address, employer, monthly
    income, and family members against the credit report's household members) agrees with
    `profile`.
  - For the ID card, every field box returned by the renderer (test-only, not in the answer key)
    contains drawn text, meaning non-background pixels.
  - Use a seed whose batch includes a zero-income pack, and assert that its bank statement shows no
    income credits.
  - `SYNTHETIC – NOT A REAL DOCUMENT` appears on every PDF page and in cell A1 of every sheet, and
    the PNG's banner region is predominantly red.
  - Every Emirates ID serial starts with `00`.
  - `answer_key.eligibility` equals `load_policy().evaluate(answer_key.facts)`, and
    `expected_routing` equals the eligibility outcome.
  - Put the per-pack document-vs-answer-key checks in a reusable helper,
    `tests/integration/pack_checks.py`, so they can run at volume. Add
    `tests/integration/test_large_batch.py`, marked `@pytest.mark.slow`, which runs them over 200
    consistent packs (SC-003).
- [ ] T015 [P] [US1] Write `tests/integration/test_determinism.py` (FR-006, SC-002, research R5):
  - Generate seed 42 with count 5 into two different roots.
  - `form.json`, `answer_key.json`, PDFs and PNGs are byte-identical; xlsx cell values are
    identical; `run.json` is identical apart from `generated_at`.
  - Seed 43 differs.
  - The run id is `s42-n5-<6 hex>` and is the same for both runs.
- [ ] T016 [P] [US1] Write `tests/integration/test_cli.py` for `generate` (contracts/cli.md),
  calling `cli.main([...])` with `capsys`:
  - Success prints the summary lines and exits 0. The output contains no name, Emirates ID or
    income from the generated packs.
  - Exit 2 with the exact messages for `--count 0`, `--count 5001`, `--seed -1`,
    `--inconsistency-rate 101`, an unknown type, `--outcome-mix 50,30,10`, and an existing run folder. In every case no new folder
    is created under `--out`.
  - `--overwrite` replaces an existing run.

### Implementation for User Story 1

- [ ] T017 [US1] Implement `src/social_support/synthetic/documents/common.py`:
  - `MARKING = "SYNTHETIC – NOT A REAL DOCUMENT"`.
  - Helpers that draw a diagonal marking and a footer on every reportlab page.
  - `money(Decimal) -> "6,000.00"` and `month_label(date)`.
  - A `RenderedDocument(path, shown: dict, field_boxes: dict | None = None)` result type. `shown`
    holds every field the document displays, in canonical form (money `"6000.00"`, dates
    `YYYY-MM-DD`), and goes into `answer_key.documents`. `field_boxes` is used only by the ID card,
    for tests, and is never written to the answer key.
- [ ] T018 [P] [US1] Implement `src/social_support/synthetic/documents/bank_statement.py` (research
  R7):
  - reportlab platypus with `invariant=1`, `Desert Falcon Demo Bank`, an account holder block.
  - 3–6 months of transactions before `as_of`: monthly credits for each income source, and debits
    for rent, utilities, groceries and loan repayments that match the liabilities.
  - A closing balance per month.
  - `shown` includes `account_holder`, `monthly_salary_credit_aed` (or the other income credits)
    and `statement_months`.
- [ ] T019 [P] [US1] Implement `src/social_support/synthetic/documents/resume.py`: reportlab with
  `invariant=1`; contact, summary, employment history (employer, title, start and end month), education
  and skills. `shown` includes `full_name`, `current_employer` and `jobs`.
- [ ] T020 [P] [US1] Implement `src/social_support/synthetic/documents/credit_report.py`:
  reportlab with `invariant=1`; `Demo Credit Information Bureau`; subject name, Emirates ID, address
  on file, a "Household members on file" table (name, relationship, age), credit score, an open
  accounts table (lender, kind, balance, status) and the number of active defaults. `shown` includes
  those fields, with `household_members` as a list.
- [ ] T021 [P] [US1] Implement `src/social_support/synthetic/documents/emirates_id.py` (research R7):
  - A 1012×638 PNG drawn with Pillow, with no metadata.
  - Titled "MOCK RESIDENT IDENTITY CARD", with a grey silhouette instead of a photo.
  - Shows name, ID number, nationality, date of birth, sex and expiry.
  - A red `SYNTHETIC` banner, and `MARKING` text.
  - `ImageFont.load_default(size=...)` only; no emblems or official titles.
  - Return `field_boxes`: the bounding box of each drawn field (name, ID number, nationality, date
    of birth, sex, expiry), for tests only.
- [ ] T022 [P] [US1] Implement `src/social_support/synthetic/documents/assets_liabilities.py`:
  - openpyxl sheets `Assets`, `Liabilities` and `Summary`.
  - Totals and net wealth stored as values, not formulas (research R7).
  - `MARKING` in A1 of each sheet; workbook created and modified dates set to `as_of`.
  - `shown` includes `total_assets_aed`, `total_liabilities_aed` and `net_wealth_aed`.
- [ ] T023 [US1] Implement `src/social_support/synthetic/pack.py`:
  - `ApplicantPack` (data-model) and `build_pack(pack_id, profile, policy, as_of, inconsistency=None)`.
  - Builds `form` (the full FR-002 fields plus the `submission` block in the exact 001 payload
    shape) and labels with `policy.evaluate(to_facts(...))`.
  - `expected_routing` is the eligibility outcome when there is no inconsistency.
  - `write_pack(pack, folder)` renders the five documents and writes `form.json` and
    `answer_key.json` in the format from [contracts/pack-format.md](./contracts/pack-format.md),
    with sorted keys, 2-space indent and money as 2-dp strings.
  - Depends on T013 and T017–T022.
- [ ] T024 [US1] Implement `src/social_support/synthetic/run.py`:
  - `GenerationRequest` with the data-model constraints verbatim: `count` 1–5000, `seed` ≥ 0,
    `inconsistency_rate_pct` 0–100 (default 0), `inconsistency_types` a non-empty subset (default
    all), `outcome_mix_pct` none or three integers summing to 100, `as_of` defaulting to
    `2026-10-01`, `output_root` defaulting to `data/synthetic`, `overwrite` defaulting to false.
    Validation raises `RequestError` with the contracts/cli.md messages.
  - Run id `s<seed>-n<count>-<sha256(canonical settings JSON)[:6]>`.
  - Refuse if the folder exists and `overwrite` is false. Write into a temporary sibling folder,
    then rename it into place (research R9).
  - `generate(request) -> GenerationRun`: loops over packs, writes `run.json` (format, run_id,
    request, generator_version, policy_version_id, generated_at ending in `Z`, counts), and logs
    progress through `services.tracing`. Add `pack_id` and `run_id` to `ALLOWED_EXTRA_KEYS` in
    `src/social_support/services/tracing.py`, since neither is personal data. Never log names, IDs or
    incomes. Add a test in `tests/integration/test_generate_batch.py` that captures the log
    records: `run_id` and `pack_id` appear, and no generated name, Emirates ID or income does.
  - Depends on T023.
- [ ] T025 [US1] Implement `src/social_support/synthetic/cli.py`:
  - `main(argv=None) -> int` with argparse subcommand `generate` taking `--count`, `--seed`,
    `--as-of`, `--out` and `--overwrite`. Accept but defer `--inconsistency-rate`,
    `--inconsistency-types` and `--outcome-mix` until US2/US3, which wire them in.
  - Map `RequestError` to exit 2 on stderr, and print the success summary from contracts/cli.md.
  - Also wire up `synthetic/__main__.py`.
  - T014–T016 now pass, except the cases that belong to US2/US3 options. Mark those tests with
    `pytest.mark.skip(reason="US2")` or `"US3"` until those phases, and remove the skips there.

**Checkpoint**: run quickstart steps 1–3. `uv run pytest` is green. Commit
"feat(002): US1 reproducible applicant packs".

---

## Phase 4: User Story 2 - Inject controlled cross-document inconsistencies (Priority: P2)

**Goal**: `--inconsistency-rate PCT --inconsistency-types ...` injects exactly
`round(PCT/100 × count)` recorded inconsistencies, one per affected pack, without changing
eligibility.

**Independent Test**: generate 100 packs at 30% income-only; exactly 30 packs show a form income
different from the bank statement, and their answer keys record the true and altered values.

### Tests for User Story 2

- [ ] T026 [P] [US2] Write `tests/unit/test_inconsistencies.py` (FR-007–FR-009, FR-011, research R8)
  and confirm it fails. It covers:
  - `select_slots` returns exactly `rate × count` slots, rounded half up (5 packs at 50% gives 3;
    100 at 30% gives 30).
  - Types are drawn only from the requested set.
  - Applicability: `INCOME_MISMATCH` needs true income > 0; `EMPLOYMENT_MISMATCH` needs EMPLOYED
    or SELF_EMPLOYED; the others always apply.
  - Each type alters the documented place: form income under-reported by 20–40%; credit-report
    address; form family size and member list with one fictional member added or removed (never
    below 1; removal only when there are members), so the form disagrees with the credit report's
    household members; ID card name misspelt or one serial digit changed with the Luhn digit
    recomputed; resume current employer.
  - `altered_value != true_value`.
  - Injection leaves `eligibility` unchanged and sets `expected_routing` to `NEEDS_HUMAN_REVIEW`.
- [ ] T027 [P] [US2] Extend `tests/integration/test_generate_batch.py` (SC-004, US2 acceptance
  scenarios 1–5):
  - 40 packs at 30% with all types: exactly 12 packs have an inconsistency. For each, the two named
    documents disagree on the named field with exactly the recorded values.
  - In every other pack, every shared field agrees across all documents, so there are no unlisted
    differences. Use the `pack_checks.py` helper from T014.
  - Every pack's `form.json["submission"]`, including the altered ones, still validates against the
    001 `SubmitApplicationRequest` schema (FR-002).
  - Add a case to the slow `tests/integration/test_large_batch.py`: 200 packs at 30% with all types
    give exactly 60 affected packs and no unlisted differences (SC-004).
  - 100 packs restricted to `address`: every injected type is `ADDRESS_MISMATCH`.
  - Remove the US2 skips in `tests/integration/test_cli.py`.

### Implementation for User Story 2

- [ ] T028 [US2] Implement `src/social_support/synthetic/inconsistencies.py`:
  - The `InconsistencyType` enum (5 types), the `Inconsistency` dataclass (data-model fields
    `type`, `documents`, `field`, `true_value`, `altered_value`), and the `applies(type, profile)`
    rules.
  - `select_slots(rng, count, rate_pct, types)` returns `{index: type}`.
  - `inject(pack_inputs, type, rng)` returns the altered form or document values plus the
    `Inconsistency`, following the table in research R8.
- [ ] T029 [US2] Add sampler constraints to `src/social_support/synthetic/profile.py`:
  `sample_profile(..., requires_income=False, requires_employment=False)`, so that slots assigned
  `INCOME_MISMATCH` or `EMPLOYMENT_MISMATCH` always get a profile where the type applies (research
  R8). Extend `tests/unit/test_profile_sampler.py` accordingly.
- [ ] T030 [US2] Wire injection into `src/social_support/synthetic/pack.py` and
  `src/social_support/synthetic/run.py`:
  - Renderers receive the altered values for the affected document only.
  - `answer_key.inconsistency` is set, and `expected_routing` is `NEEDS_HUMAN_REVIEW`.
  - `run.json` counts add `expected_routing` and `inconsistencies` per type.
- [ ] T031 [US2] Wire `--inconsistency-rate` and `--inconsistency-types` (comma list: `income`,
  `address`, `family_size`, `identity`, `employment`) into `src/social_support/synthetic/cli.py`,
  with the contract's error messages and the `Inconsistencies:` summary line.

**Checkpoint**: run quickstart step 4. `uv run pytest` is green. Commit
"feat(002): US2 inconsistency injection".

---

## Phase 5: User Story 3 - Export a labelled dataset for model training (Priority: P3)

**Goal**: every run writes `summary.csv`; `--outcome-mix A,D,R` controls the share of each
eligibility outcome, met exactly through largest-remainder quotas.

**Independent Test**: generate with `--outcome-mix 40,40,20`; `summary.csv` has one row per pack,
matches the answer keys, and has the requested outcome counts.

### Tests for User Story 3

- [ ] T032 [P] [US3] Write `tests/unit/test_allocation.py` (FR-013, research R4, edge case on
  rounding) and confirm it fails. It covers:
  - Largest-remainder quotas sum to `count`, and each differs from the exact share by less than 1.
  - Examples: 10 packs at 33/33/34 gives 3/3/4; 500 at 40/40/20 gives 200/200/100; a 0% outcome
    gives 0.
  - The slot order is deterministic for a given seed.
- [ ] T033 [P] [US3] Extend `tests/unit/test_profile_sampler.py` (SC-005) and confirm it fails:
  - For each target outcome, `sample_profile(..., target=outcome)` labels to that outcome.
  - 500 sampled profiles (no rendering) with mix 40/40/20 give exactly 200/200/100.
  - The average attempts per pack stay under 5, and the cap of 200 attempts raises `SamplingError`
    naming the outcome (force this with an unsatisfiable `tmp_path` policy).
  - `target=APPROVE` combined with `requires_employment=True` still succeeds.
- [ ] T034 [P] [US3] Write `tests/integration/test_dataset.py` (FR-014, US3 scenarios 1–4,
  [contracts/pack-format.md](./contracts/pack-format.md#summarycsv)). Generate 30 packs with mix
  40,40,20 and 20% inconsistencies, then assert:
  - `summary.csv` has 30 rows in pack id order, with the exact column list and order from the
    contract.
  - Each row equals its `answer_key.json` facts and labels.
  - Outcome counts are 12/12/6.
  - Nationality and gender appear only as `audit_nationality` and `audit_gender`, and no other
    column name matches a protected attribute.
  - Remove the US3 skips in `tests/integration/test_cli.py`.

### Implementation for User Story 3

- [ ] T035 [US3] Implement `src/social_support/synthetic/allocation.py`: `quotas(count, mix_pct)`
  using the largest-remainder method (ties broken in the order APPROVE, SOFT_DECLINE,
  NEEDS_HUMAN_REVIEW), and `assign_targets(rng, quotas) -> list[Outcome]`, shuffled with the run's
  random generator.
- [ ] T036 [US3] Add outcome-targeted sampling to `src/social_support/synthetic/profile.py`
  (research R4):
  - Priors tuned per target outcome: for example, APPROVE draws low income per member, no
    defaults, a score of 550 or more and modest wealth; SOFT_DECLINE draws high income per member
    or high wealth; NEEDS_HUMAN_REVIEW draws borderline income, a poor score, defaults, or low
    income with unstable work.
  - Rejection loop: label with the policy and retry until the label matches, at most 200 attempts,
    then raise `SamplingError`.
  - The label always comes from `policy.evaluate`, never from the target.
- [ ] T037 [US3] Implement `src/social_support/synthetic/dataset.py`: `write_summary(run_folder,
  packs)` builds a pandas DataFrame with the contract's columns in order (`audit_` columns last)
  and writes `summary.csv` (UTF-8, no index). Call it from `run.generate`, and add the per-outcome
  eligibility counts to `run.json`.
- [ ] T038 [US3] Wire `--outcome-mix A,D,R` into `src/social_support/synthetic/cli.py` and
  `run.py`, with the contract's error message and the `Eligibility:` summary line. When no mix is
  given, use natural sampling.

**Checkpoint**: run quickstart step 5. `uv run pytest` is green. Commit
"feat(002): US3 labelled dataset export".

---

## Phase 6: User Story 4 - Seed the running application with generated applicants (Priority: P4)

**Goal**: `social-support-data seed --run DIR` submits each pack's `submission` block to the 001
API and writes `seeding_report.csv`; it stops cleanly when the API is unreachable.

**Independent Test**: seed 20 packs into the running app, then look up 3 reference numbers with
their Emirates IDs.

### Tests for User Story 4

- [ ] T039 [P] [US4] Write `tests/integration/test_seeding.py` (FR-019, FR-020, research R11) and
  confirm it fails. The 001 app runs in-process: build `ApiClient(base_url="http://testserver",
  transport=<TestClient from make_client()>._transport)`. Cases:
  - 5 packs: 5 `submitted` rows with reference numbers, `returned_outcome` and
    `eligibility_outcome` filled, and `matched` correct.
  - The API is unreachable on the 3rd request (a transport that raises `httpx.ConnectError`): exit
    code 1, the contract message, and the report lists only the 2 submitted packs.
  - A pack whose `submission` was edited to be invalid gets status `rejected` and seeding
    continues.
  - `seed --run` on a folder without `run.json` exits 2 with `not a generated run: <path>`.
  - The console output contains no names, Emirates IDs or incomes.
- [ ] T040 [P] [US4] Write `tests/e2e/test_generate_seed_lookup.py` (Principle V end-to-end, US4
  scenario 2, SC-008):
  - Generate 50 packs with seed 5, then seed them into the in-process 001 app.
  - All 50 are accepted with reference numbers (SC-008).
  - For 3 of them, `POST /api/v1/applications/lookup` with the reference and the pack's Emirates
    ID returns the stored details equal to `form.json["submission"]`.

### Implementation for User Story 4

- [ ] T041 [US4] Implement `src/social_support/synthetic/seeding.py`:
  - `seed_run(run_folder, client: ApiClient, limit=None) -> SeedingSummary` posts packs in pack id
    order.
  - On `ApiError` with `status_code == 0` (unreachable), stop and record nothing further.
  - On 422, record `rejected`.
  - Write `seeding_report.csv` with the columns `pack_id, status, reference_number,
    returned_outcome, eligibility_outcome, matched` (data-model SeedingResult) containing only
    attempted packs.
  - Log only pack ids, reference numbers and counts.
- [ ] T042 [US4] Add the `seed` subcommand to `src/social_support/synthetic/cli.py`: `--run`,
  `--limit` and `--api-base-url` (default: `ApiClient()`'s own environment, then `.env`, then the
  default resolution). Print the contract messages, and use exit codes 0, 1 and 2.

**Checkpoint**: run quickstart step 7 against the live API. `uv run pytest` is green. Commit
"feat(002): US4 seed the running application".

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T043 [P] Write `tests/integration/test_generation_speed.py`, marked `@pytest.mark.slow`
  (SC-001): 100 packs with default settings finish in under 300 s. Run it with
  `uv run pytest -m slow` and record the measured time in the Notes below.
- [ ] T044 [P] Update `README.md` with a "Synthetic data" section: the commands from quickstart
  steps 2–7, the output layout, the two labels, and the privacy notes (synthetic marking, reserved
  ID block, git-ignored output). Also add the commands and the `labelling` / `synthetic` layering
  rules to `CLAUDE.md`. Edit only these sections; leave the user's other README changes as they
  are.
- [ ] T045 Run the full [quickstart.md](./quickstart.md) (steps 1–8) on a clean `data/synthetic/`.
  Open one pack's five documents by eye: they must be readable and synthetic-marked, with no real
  branding. Record the results in the Notes below.
- [ ] T046 Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest` and
  `uv run pytest -m slow`, and confirm all are green. Then run `/speckit-converge`.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (T001–T003)**: T002 needs T001.
- **Foundational (T004–T013)**: depends on Setup and **blocks every story**. Internal order:
  1. T004 and T005, then T006, then T007.
  2. T008 needs T002, and is completed once T006 and T013 exist.
  3. T009 and T010, then T011.
  4. T012, plus T005 and T011, then T013.
- **US1 (T014–T025)**: depends on Foundational. The renderers T018–T022 depend on T017. Then T023,
  then T024, then T025.
- **US2 (T026–T031)**: depends on US1, because it changes `pack.py`, `run.py` and `cli.py`.
- **US3 (T032–T038)**: depends on US1. It can run in parallel with US2 only if the edits to
  `profile.py`, `run.py` and `cli.py` are serialised.
- **US4 (T039–T042)**: depends on US1 only, since it reads a run folder.
- **Polish (T043–T046)**: depends on all the stories you intend to deliver.

### Shared files (no [P] across these, even between stories)

- `src/social_support/synthetic/profile.py`: T013, T029, T036
- `src/social_support/synthetic/pack.py`: T023, T030
- `src/social_support/synthetic/run.py`: T024, T030, T037, T038
- `src/social_support/synthetic/cli.py`: T025, T031, T038, T042
- `tests/unit/test_profile_sampler.py`: T012, T029, T033
- `tests/integration/test_generate_batch.py`: T014, T024, T027
- `tests/integration/test_large_batch.py` and `tests/integration/pack_checks.py`: T014, T027
- `src/social_support/services/tracing.py`: T024
- `tests/integration/test_cli.py`: T016, T027, T034

### Within each story

Write the tests first and confirm they fail, then implement in this order: pure logic → renderers →
pack → run → CLI. Commit at each checkpoint.

---

## Parallel Examples

```text
# Phase 2: independent files
T004 test_labelling_policy.py | T005 facts.py | T009 test_identities.py | T010 names.toml | T012 test_profile_sampler.py

# US1: tests together, then the five renderers together (after T017)
T014 test_generate_batch.py | T015 test_determinism.py | T016 test_cli.py
then: T018 bank_statement.py | T019 resume.py | T020 credit_report.py | T021 emirates_id.py | T022 assets_liabilities.py

# US2 / US3 / US4 tests can be written in parallel with each other
T026 | T027 | T032 | T033 | T034 | T039 | T040
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1, then Phase 2, then Phase 3 (US1).
2. **Stop and validate**: quickstart steps 1–3 and `uv run pytest`.
3. Commit. This alone gives feature 003 (extraction) readable documents and an answer key.

### Incremental delivery

1. US2 (inconsistencies): quickstart step 4, then commit. Unblocks feature 004 (validation).
2. US3 (dataset): quickstart step 5, then commit. Unblocks feature 005 (ML).
3. US4 (seeding): quickstart step 7, then commit. Demo support.
4. Polish, then the full quickstart, then `/speckit-converge`.

---

## Notes

- `[P]` means a different file with no dependency on an incomplete task.
- Every task maps to an FR, an SC or a research decision, so `/speckit-analyze` can check coverage.
- Synthetic data only (Constitution I). Generated output goes under `data/synthetic/`, which is
  git-ignored, and never into `tests/fixtures/`. Tests generate into `tmp_path`.
