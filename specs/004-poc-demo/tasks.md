---

description: "Task list for feature 004: PoC Demo — Documents to Decision and Enablement"
---

# Tasks: PoC Demo — Documents to Decision and Enablement

**Input**: Design documents from `/specs/004-poc-demo/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: included. Constitution Principle V requires cross-checks and decision rules to be built
test-first, the LLM to be mocked in tests, and one end-to-end test over synthetic data. Test tasks
come before their implementation and MUST fail first.

**Organization**: grouped by user story. The demo packs (US5) are built in the Foundational phase
because every other story's tests upload them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1–US5, matching spec.md
- Paths are relative to the repository root

---

## Phase 1: Setup

**Purpose**: dependencies and configuration

- [ ] T001 Add runtime dependencies in `pyproject.toml`: move `pypdf` from the dev group to
  `dependencies`, add `rapidocr-onnxruntime>=1.4.4,<1.5` and `python-multipart`; run `uv sync` and
  commit `uv.lock`
- [ ] T002 [P] Add settings to `src/social_support/config.py`: `upload_dir: Path = Path("data/uploads")`,
  `income_tolerance_pct: Decimal = Decimal("10")`, `ocr_min_confidence: float = 0.80`,
  `ollama_url: str = "http://localhost:11434"`,
  `enablement_model: str = "qwen2.5:7b"`, `enablement_timeout_s: float = 90`,
  `decision_policy: str = "decision_v1"`; document all of them in `.env.example`
- [ ] T003 [P] Add `data/uploads/` and `data/demo/` to `.gitignore`

---

## Phase 2: Foundational (blocks all stories)

**Purpose**: domain types, storage, the rule engine extension and the demo packs (US5)

- [ ] T004 [P] Create `src/social_support/domain/documents.py`:
  - `DocumentType` StrEnum (`BANK_STATEMENT`, `EMIRATES_ID_CARD`, `RESUME`, `ASSETS_LIABILITIES`,
    `CREDIT_REPORT`) with `label` and `field_name` properties (`bank_statement`, `emirates_id_card`,
    `resume`, `assets_liabilities`, `credit_report`);
  - frozen `ExtractedDocument(document_type, ok, fields: dict[str, str], items: dict[str,
    tuple[str, ...]], confidence: dict[str, float], error: str | None, duration_ms: int)`;
  - `CrossCheckResult(check_id, passed: bool | None, form_value, document_value, sources, message)`;
  - `Finding(rule_id, outcome, text, sources)`;
  - `CaseAssessment(result: AssessmentResult, findings: tuple[Finding, ...])`;
  - `REQUIRED_FIELDS` per type, exactly as listed in data-model.md.
- [ ] T005 [P] Add `EXTRACTED`, `CROSS_CHECKED` and `ENABLEMENT` to `TraceStep` in
  `src/social_support/domain/models.py`; add the whitelisted log keys `document_type`, `check_id`,
  `model`, `is_fallback` and `latency_ms` in `src/social_support/services/tracing.py`. Trace
  `detail` formats per data-model.md: EXTRACTED `BANK_STATEMENT ok 140ms; …`; ENABLEMENT
  `<model> <latency_ms>ms` or `fallback <error_type>`; never identity or amounts
- [ ] T006 Add ORM tables to `src/social_support/persistence/orm.py`, all append-only, existing
  tables untouched:
  - `application_documents`: application_id FK, document_type, original_filename, stored_path,
    sha256 String(64), size_bytes, ok, error nullable, fields JSON, items JSON, confidence JSON,
    duration_ms;
  - `cross_check_results`: application_id FK, check_id, passed nullable, form_value, document_value,
    message Text;
  - `decision_inputs`: decision_id FK unique, facts JSON nullable, fact_sources JSON;
  - `decision_findings`: decision_id FK, sequence, rule_id, outcome, text Text, sources JSON;
  - `enablement_plans`: application_id FK, created_at, model, is_fallback, profile JSON,
    latency_ms, error_type nullable, training JSON, job_matches JSON, career_counselling Text.
- [ ] T007 Extend `ApplicationRepository` in `src/social_support/persistence/repository.py`:
  - `add_submission` takes optional `documents`, `cross_checks`, `inputs` and `findings` and stores
    them in the same transaction;
  - add `get_documents`, `get_cross_checks`, `get_findings(decision_id)`, `add_enablement_plan` and
    `get_enablement_plan(application_id)` (latest);
  - add or get only, never update or delete.
- [ ] T008 [P] Test first, in `tests/unit/test_labelling_policy.py` (extend): `evaluate_all` returns
  every matching non-default rule in file order, never the default rule, and an empty list when only
  the default matches
- [ ] T009 Implement `LabellingPolicy.evaluate_all(facts) -> list[LabelResult]` in
  `src/social_support/labelling/policy.py`; leave `evaluate` unchanged
- [ ] T010 [P] [US5] Create `src/social_support/synthetic/demo.py`:
  - three hand-built `HouseholdProfile`s (pack indexes 901–903, as-of 2026-10-01) per research R8:
    - approve: family 5, salary 6000.00, Sales Associate, 20 or more months employed, net wealth
      about 30 000, score 720, 0 defaults;
    - soft_decline: family 2, salary 18000.00, Project Manager, property worth 750 000, score 760;
    - review: family 4, income 9000.00, stable job, score 690, form income set to 7000.00 and
      recorded as an `INCOME_MISMATCH` inconsistency;
  - `write_demo(out: Path, force: bool) -> list[tuple[str, Outcome, dict]]` using `build_pack` and
    `write_pack`;
  - give each profile realistic, distinct skills so the enablement output differs.
- [ ] T011 [US5] Add the `demo` subcommand (`--out data/demo`, `--force`; exits 2 if packs exist and
  `--force` is not given; prints folder, expected outcome and form values) in
  `src/social_support/synthetic/cli.py` per contracts/cli.md
- [ ] T012 [P] [US5] Test in `tests/integration/test_demo_packs.py` (writes to `tmp_path`): three
  folders, each with 7 files; byte-identical on a second run; each `answer_key.json`
  `expected_routing` is APPROVE / SOFT_DECLINE / NEEDS_HUMAN_REVIEW respectively; exits 2 without
  `--force`
- [ ] T013 Add a `demo_packs` session-scoped fixture to `tests/conftest.py` that writes the three
  packs once to a temp folder, and make `make_client` default `upload_dir` to a per-test temp folder
  (advisor injection is added in T047)

**Checkpoint**: `uv run social-support-data demo` produces the three packs, and the foundation tests pass.

---

## Phase 3: User Story 1 — Auto-approval from uploaded documents (P1) 🎯 MVP

**Goal**: form plus five files → extraction → cross-checks → APPROVE with one positive reason per
factor, each citing its source document.

**Independent Test**: submit the approve demo pack through the API and the UI; the outcome is
APPROVE, 4 cross-checks pass, and extracted values are listed per document.

### Tests for User Story 1 ⚠️ write first, must fail

- [ ] T014 [P] [US1] Parser unit tests on text fixtures (copied from real pypdf output of a demo
  pack) in `tests/unit/test_parsers.py`:
  - bank statement: account holder, average of "Total credits", last closing balance;
  - credit report: score, defaults, report date, name;
  - resume: jobs with `Present`, months employed in the last 24 relative to the report date (match
    `synthetic.profile.months_employed_last_24` for the same jobs), years of experience, skills split
    on commas across wrapped lines;
  - ID card: parsing an OCR line list of `(text, score)` including captions without spaces
    (`ExpiryDate`) and the pattern `784-\d{4}-\d{7}-\d`; per-field confidence kept; a required field
    scored 0.79 with threshold 0.80 gives `ok=False` with "read with low confidence" (FR-016).
- [ ] T015 [P] [US1] Cross-check unit tests in `tests/unit/test_crosschecks.py`:
  - names are compared case- and whitespace-insensitively;
  - Emirates IDs are compared as digits only;
  - income passes at exactly 10% and fails above it;
  - `passed=None` when the needed document is not ok.
- [ ] T016 [P] [US1] Decision unit tests in `tests/unit/test_decision_rules.py` for the APPROVE path:
  `assess_case(facts, findings=())` with income per member 1200, net wealth 30 000, score 720,
  0 defaults, 20 months → APPROVE, with findings `income_within_band`, `wealth_within_limit`,
  `credit_good_standing` and `stable_work`, each with source labels and each text containing its
  threshold (FR-009)
- [ ] T017 [P] [US1] Extraction integration test in `tests/integration/test_extraction_demo_packs.py`:
  for all three demo packs (real OCR), every required field equals the `answer_key.json` document
  view (money compared as Decimal)
- [ ] T018 [P] [US1] Contract test in `tests/contract/test_documents_contract.py` for `POST
  /api/v1/applications/with-documents`:
  - 201 shape per contracts/api.md;
  - 422 `{"errors":[{"field":"resume",…}]}` when one file is missing;
  - `decision.findings` present on the 001 JSON submit too.

### Implementation for User Story 1

- [ ] T019 [P] [US1] `src/social_support/extraction/pdf_text.py`: `pdf_text(data: bytes) -> str`
  with pypdf; raises `ExtractionError` on unreadable PDFs
- [ ] T020 [P] [US1] `src/social_support/extraction/bank_statement.py`, `credit_report.py` and
  `assets_liabilities.py` (openpyxl, "Summary" sheet totals): each `parse(data) -> ExtractedDocument`,
  `ok=False` with an error when a REQUIRED field is missing
- [ ] T021 [P] [US1] `src/social_support/extraction/resume.py`: parse job lines `Title, Employer (Mon
  YYYY - Mon YYYY|Present)`, education line, skills; take the as-of from the caller (the credit report
  date) and compute `months_employed_last_24` and `years_experience` per research R4; no import of
  `synthetic`
- [ ] T022 [P] [US1] `src/social_support/extraction/emirates_id.py`: a lazy module-level RapidOCR
  engine; `parse_ocr_lines(lines: list[tuple[str, float]], min_confidence)` (pure, for unit tests)
  and `parse(data, min_confidence)`; accept PNG/JPEG only; keep each field's OCR score in
  `confidence`; `ok=False` with "read with low confidence" when a required field is below
  `min_confidence` (FR-016)
- [ ] T023 [US1] `src/social_support/extraction/__init__.py`: `extract_all(files: dict[DocumentType,
  bytes]) -> dict[DocumentType, ExtractedDocument]`:
  - checks magic bytes and the 10 MB limit first;
  - parses the credit report before the resume so its date is the as-of;
  - catches every exception per document into `ok=False`;
  - measures `duration_ms` per document (FR-017).
- [ ] T024 [US1] `src/social_support/domain/crosschecks.py`: `run_crosschecks(form, documents,
  tolerance_pct) -> list[CrossCheckResult]` for `name_vs_id_card`, `emirates_id_vs_id_card`,
  `name_vs_bank_holder` and `income_vs_bank`
- [ ] T025 [US1] `src/social_support/labelling/policies/decision_v1.toml` with the APPROVE finding
  rules (`income_within_band` < 2000, `wealth_within_limit` ≤ 500000, `credit_good_standing` score ≥ 550
  and defaults eq 0, `stable_work` months ≥ 12, `not_in_work` status in UNEMPLOYED/STUDENT/RETIRED),
  self-contained bounds, plus the default rule; every reason template states the value and its
  threshold (FR-009)
- [ ] T026 [US1] `src/social_support/assessment/document_rules.py`: `DocumentRuleAssessor.assess_case(
  facts: HouseholdFacts | None, findings: tuple[Finding, ...]) -> CaseAssessment`. It never receives
  `ExtractedDocument`, `CrossCheckResult`, names or ID numbers (research R6). When `facts` is
  present it:
  - calls `evaluate_all` and attaches the fixed source label per factor (income → Bank statement,
    wealth → Assets/liabilities, credit → Credit report, months employed → Resume, family size and
    status → Application form);
  - merges these with the given findings;
  - picks the worst outcome (review > soft decline > approve);
  - returns `CaseAssessment` with its `rule_version` from the policy version id.

  In `src/social_support/services/applications.py`, add `build_facts(submission, documents) ->
  tuple[HouseholdFacts | None, failed_types]`.
- [ ] T027 [US1] `src/social_support/services/uploads.py`: `store_files(upload_dir, reference,
  files) -> list[StoredFile]` (sha256, size, path `<reference>/<document_type><ext>`); called after
  the DB commit; on a write failure add a FAILED `STORED` trace step with `error_type`, and the
  decision stands
- [ ] T028 [US1] `ApplicationService.submit_with_documents(submission, files)` in
  `src/social_support/services/applications.py`:
  - trace steps EXTRACTED and CROSS_CHECKED;
  - builds the facts and the pre-built findings, then calls `assess_case`;
  - stores documents, cross-checks, `decision_inputs` (facts and fact_sources) and findings with
    the decision (FR-010);
  - falls back to NEEDS_HUMAN_REVIEW on an assessor exception, as today;
  - registers the decision policy rule version at startup in `src/social_support/api/main.py`.
- [ ] T029 [US1] Schemas `DocumentOut`, `CrossCheckOut`, `FindingOut` and the `findings` field on
  `DecisionOut` in `src/social_support/api/schemas.py`; route `POST /applications/with-documents` in
  `src/social_support/api/routes.py`, with form fields via `Form`, files via `UploadFile`, and
  missing files reported in the flat `errors` shape
- [ ] T030 [US1] `ApiClient.submit_with_documents(payload, files)` (timeout 120 s) in
  `src/social_support/ui/client.py`
- [ ] T031 [US1] Apply tab in `src/social_support/ui/app.py`:
  - the form gains 5 `st.file_uploader`s with labelled types;
  - the result shows the outcome badge, a findings list with sources, a cross-check table (✓/✗/–),
    and one expander per document with its extracted values;
  - a spinner while processing.
- [ ] T032 [US1] Integration test in `tests/integration/test_submit_with_documents.py`: the approve
  pack → APPROVE; rows exist in `application_documents` (with `duration_ms`), `cross_check_results`,
  `decision_inputs` and `decision_findings`; files are stored under `upload_dir` with matching
  sha256; logs contain no name, ID or income

**Checkpoint**: the approve demo works end-to-end in the UI.

---

## Phase 4: User Story 2 — Soft decline with reasons (P1)

**Goal**: households clearly outside the criteria get SOFT_DECLINE with every failing factor and
next steps.

**Independent Test**: submit the soft_decline pack; SOFT_DECLINE cites income per member above 2500
and net wealth above 500 000 and includes next steps.

- [ ] T033 [P] [US2] Tests in `tests/unit/test_decision_rules.py`:
  - income per member 9000 and net wealth 650 000 → SOFT_DECLINE with both findings and at least one
    next step;
  - approve findings that also hold are still listed but do not change the outcome.
- [ ] T034 [US2] Add the rules `income_above_band` (> 2500) and `high_net_wealth` (> 500000) as
  SOFT_DECLINE to `src/social_support/labelling/policies/decision_v1.toml`; add next-step text per
  rule (reapply when circumstances change; enablement support is still offered) in
  `src/social_support/assessment/document_rules.py`
- [ ] T035 [US2] Show the next steps under the SOFT_DECLINE findings in
  `src/social_support/ui/app.py`, using the existing `suggested_next_steps` rendering
- [ ] T036 [US2] Extend `tests/integration/test_submit_with_documents.py` so the soft_decline pack
  → SOFT_DECLINE with both rule ids

---

## Phase 5: User Story 3 — Human review with reasons (P1)

**Goal**: uncertain cases (borderline income, mismatches, credit problems, unstable work, unreadable
documents) go to NEEDS_HUMAN_REVIEW with all reasons and appear in the caseworker queue.

**Independent Test**: submit the review pack → NEEDS_HUMAN_REVIEW with borderline income and income
mismatch reasons; it is listed in the review queue with both; a PDF in the ID card slot gives a
review with an "ID card unreadable" reason.

- [ ] T037 [P] [US3] Tests in `tests/unit/test_decision_rules.py`:
  - borderline income 2250 → review;
  - defaults ≥ 1 → review;
  - score 520 → review;
  - EMPLOYED with 8 months → review;
  - a failed cross-check finding → review even when the rules say APPROVE;
  - a failed document → review, rules skipped, one `document:<type>` finding;
  - review plus soft-decline findings → review, with all findings listed.
- [ ] T038 [P] [US3] Add a broken-file fixture set in `tests/fixtures/broken_files.py` (empty bytes,
  truncated PDF, PDF bytes for the ID card, 10 MB + 1 byte) and an integration test in
  `tests/integration/test_submit_with_documents.py`: each → 201 NEEDS_HUMAN_REVIEW naming the document
- [ ] T039 [US3] Add the rules `borderline_income` (≥ 2000 and ≤ 2500), `active_credit_defaults`
  (≥ 1), `poor_credit_score` (< 550) and `unstable_work_history` (months < 12 and status in
  EMPLOYED/SELF_EMPLOYED) as NEEDS_HUMAN_REVIEW to
  `src/social_support/labelling/policies/decision_v1.toml`
- [ ] T040 [US3] In `src/social_support/services/applications.py` (not the assessor, so identity
  stays out of it), turn failed cross-checks into `crosscheck:<id>` findings and not-ok documents
  (including low OCR confidence) into `document:<type>` findings, both NEEDS_HUMAN_REVIEW, citing
  both values and the documents, and pass them to `assess_case`. In
  `src/social_support/assessment/document_rules.py`, `flag_reason` = the review finding texts
  joined with "; " and truncated to 200 chars
- [ ] T041 [US3] Add `reasons: list[str]` to the review queue items in
  `src/social_support/services/applications.py`, `src/social_support/api/schemas.py` and
  `src/social_support/api/routes.py`; show them in the Review queue tab in
  `src/social_support/ui/app.py`; update `tests/contract/test_review_queue_contract.py`
- [ ] T042 [US3] Extend `tests/integration/test_submit_with_documents.py`: the review pack →
  NEEDS_HUMAN_REVIEW with `borderline_income` and `crosscheck:income_vs_bank`, and it appears in
  `/review-queue` with both reasons

---

## Phase 6: User Story 4 — Economic enablement recommendations (P2)

**Goal**: an LLM-written training, job-matching and counselling plan from the anonymised profile,
with a labelled fallback; the decision is never affected.

**Independent Test**: with Ollama running, the plan references the applicant's skills or role; with
Ollama stopped, the fallback is labelled and the decision is identical.

- [ ] T043 [P] [US4] Create `src/social_support/domain/enablement.py`:
  - `EnablementProfile` (skills, education, years_experience, last_job_title, employment_status,
    months_employed_last_24, family_size, outcome, income_band in
    `below_band|borderline|above_band|unknown`);
  - `EnablementPlan(training, job_matches, career_counselling, is_fallback, model)`;
  - the `EnablementAdvisor` protocol;
  - `FALLBACK_PLAN` with general UAE-neutral advice and `model="fallback"`.
- [ ] T044 [P] [US4] Tests in `tests/unit/test_enablement_advisor.py` with an `httpx.MockTransport`:
  - a valid JSON answer → plan;
  - missing keys, empty lists or non-JSON → raises;
  - a timeout → raises;
  - the request body contains none of the name, Emirates ID, employer or exact income (check against
    the review pack values);
  - at most 5 items per list.
- [ ] T045 [US4] `src/social_support/enablement/ollama.py`: `OllamaEnablementAdvisor(url, model,
  timeout_s, transport=None)` that POSTs `/api/chat` with `format: "json"`, `stream: false`,
  `options.temperature` 0.3, a system prompt (career adviser for a social-support programme; answer
  only JSON with keys training, job_matches, career_counselling) and the profile JSON as the user
  message; it validates the answer per research R7
- [ ] T046 [US4] `build_enablement_profile(documents, submission, assessment)` and
  `ApplicationService.enablement_for(reference, emirates_id)` in
  `src/social_support/services/applications.py`:
  - the identity check is the same as lookup (`None` → 404);
  - return the stored plan if present;
  - otherwise call the advisor, timing it, and fall back to `FALLBACK_PLAN` on any exception;
  - store the plan with the exact profile sent, `latency_ms` and `error_type` (FR-017);
  - add the ENABLEMENT trace step, and log `model`, `is_fallback` and `latency_ms` only.
- [ ] T047 [US4] Route `POST /api/v1/applications/{reference_number}/enablement` and `EnablementOut`
  in `src/social_support/api/routes.py` and `schemas.py`; build the advisor from settings in
  `create_app(settings, assessor=None, advisor=None)` in `src/social_support/api/main.py`; add an
  `advisor=` option to `make_client` in `tests/conftest.py`; add `enablement_model` to `/health`
- [ ] T048 [US4] Integration test in `tests/integration/test_enablement_flow.py`:
  - fake advisor → stored plan with `profile` and `latency_ms`, and a second call does not call the
    advisor;
  - failing advisor → `is_fallback` true and the decision row is unchanged;
  - unknown reference and wrong ID give identical 404 bodies.
- [ ] T049 [US4] `ApiClient.enablement(reference, emirates_id)` (timeout 150 s) in
  `src/social_support/ui/client.py`; in `src/social_support/ui/app.py`, after the decision renders,
  show a "Preparing your economic enablement plan…" spinner and three sections (Training & upskilling,
  Job matches, Career counselling) with a caption naming the model or "General guidance (model
  unavailable)"

---

## Phase 7: Polish & Cross-Cutting

- [ ] T050 [P] Architecture guards in `tests/unit/test_architecture.py`:
  - `extraction` and `enablement` import no `persistence`, `services`, `api`, `ui` or `synthetic`;
  - `domain` still imports no httpx or rapidocr;
  - `ui` still imports no `social_support` packages;
  - `DocumentRuleAssessor.assess_case` has no parameter annotated with `ExtractedDocument`,
    `CrossCheckResult` or `Submission`, and `assessment` does not import `domain.documents`
    beyond `Finding` and `CaseAssessment` (identity boundary).
- [ ] T051 End-to-end test in `tests/e2e/test_demo_packs_end_to_end.py`: generate the demo packs →
  submit all three through `ApiClient` over the in-process app (real OCR, fake advisor) → outcomes
  APPROVE / SOFT_DECLINE / NEEDS_HUMAN_REVIEW, the enablement call succeeds, and the review queue holds
  exactly the review pack (SC-001)
- [ ] T052 [P] Manual timing check per quickstart scenario 1–2 on the laptop (decision < 30 s,
  enablement < 90 s with `qwen2.5:7b`); if the enablement is too slow, set `ENABLEMENT_MODEL=qwen2.5:3b`
  in `.env.example` and note it in `specs/004-poc-demo/research.md` R7
- [ ] T053 [P] Update `README.md` with step-by-step demo instructions (Ollama check, `demo` command,
  API, UI, the three scenarios, the review queue) and `CLAUDE.md` (feature 004 status, new
  packages, `demo` command, new settings, the decision policy)
- [ ] T054 Run `uv run ruff check .`, `uv run ruff format .` and `uv run pytest`, then walk through
  `specs/004-poc-demo/quickstart.md` scenarios 1–7 in the real UI

---

## Dependencies & Execution Order

### Phase dependencies
- Setup (T001–T003) → Foundational (T004–T013) → US1 (T014–T032) → US2 and US3 (can run in parallel
  once US1's assessor exists) → US4 (needs only the US1 submission and storage) → Polish.

### Story dependencies
- **US5** (demo packs) is in Foundational: every story's tests upload them.
- **US1** builds the whole pipeline; US2 and US3 only add rules, findings and UI on top.
- **US4** depends on US1 (stored documents and decision), not on US2 or US3.

### Within each story
- Tests are written first and fail → extractors and domain → assessor → service → API → UI.
- T023 depends on T019–T022; T026 depends on T009 and T025; T028 depends on T007, T023, T024, T026
  and T027; T047 extends the `make_client` from T013.

### Parallel opportunities
- T002 and T003; T004 and T005; T008 and T010.
- US1 tests T014–T018 together; extractors T019–T022 together.
- US2 (T033–T036) and US3 (T037–T042) touch the same TOML and assessor, so run them one after the
  other, or coordinate on `decision_v1.toml`.
- US4 T043 and T044 can start as soon as US1's T028 is done.

## Parallel Example: User Story 1

```text
T014 tests/unit/test_parsers.py        T019 extraction/pdf_text.py
T015 tests/unit/test_crosschecks.py    T020 extraction/bank_statement.py, credit_report.py, assets_liabilities.py
T016 tests/unit/test_decision_rules.py T021 extraction/resume.py
T017 tests/integration/...demo_packs   T022 extraction/emirates_id.py
```

## Implementation Strategy

1. **Day 1**: Setup, Foundational and US1 → the approve demo works in the UI (MVP; you could present
   this alone).
2. **Day 2**: US2 and US3 → all three decision scenarios plus the review queue.
3. **Day 3**: US4 → LLM enablement with fallback.
4. **Day 4**: Polish, the end-to-end test, README, and timing rehearsal.

## Notes

- Never log names, Emirates IDs or incomes; only whitelisted `extra` keys.
- Money is `Decimal` internally and a 2-dp string in JSON; timestamps are UTC with a `Z` suffix.
- The repository stays add/get only.
- Tests never write to `data/`; use `tmp_path`.
