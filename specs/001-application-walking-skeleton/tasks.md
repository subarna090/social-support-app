---

description: "Task list for feature 001: Application Walking Skeleton"
---

# Tasks: Application Walking Skeleton

**Input**: Design documents from `/specs/001-application-walking-skeleton/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api.md](./contracts/api.md), [quickstart.md](./quickstart.md)

**Tests**: included. They are required by Constitution Principle V (test-first for validation and
decision logic, plus an end-to-end test for each feature) and by success criteria SC-004, SC-005
and SC-006. Test tasks come before their implementation tasks and MUST fail before the
implementation is written.

**Organization**: Tasks are grouped by user story so that each story can be implemented and
tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 / US2 / US3, matching the user stories in spec.md
- Paths are relative to the repository root and use the single `src/` layout from plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling

- [ ] T001 Create `pyproject.toml` at the repo root:
  - Project name `social-support`, `src/` layout, package `social_support`,
    `requires-python = ">=3.12,<3.13"`.
  - Runtime dependencies: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `pydantic-settings`,
    `sqlalchemy>=2`, `streamlit`, `httpx`.
  - A `[dependency-groups] dev` group with `pytest` and `ruff`.
  - Also create `.python-version` containing `3.12`.
- [ ] T002 Create the package and test skeleton from plan.md, with empty `__init__.py` files:
  - `src/social_support/{domain,assessment,persistence,services,api,ui}/`
  - `tests/{unit,contract,integration,ui,fixtures}/`
- [ ] T003 Add tool configuration to `pyproject.toml`:
  - `[tool.ruff]`: line-length 100, target `py312`, lint rule sets `E,F,I,B,UP`.
  - `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["src"]`.
- [ ] T004 [P] Create `.env.example` documenting `DATABASE_URL=sqlite:///./data/app.db`,
  `CASEWORKER_PASSCODE=` (left empty), `ASSESSOR=income_rule`, `RULE_THRESHOLD_AED=2000`,
  `RULE_BAND_UPPER_AED=2500` and `API_BASE_URL=http://127.0.0.1:8000`. Add `data/` to `.gitignore`.
- [ ] T005 Run `uv sync` to create `.venv` with Python 3.12 and generate `uv.lock`. Confirm that
  `uv run python -c "import social_support"` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuration, domain types, validation, persistence, tracing and the app shell,
which every story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T006 [P] Implement `Settings` (pydantic-settings, reading `.env`) and a cached `get_settings()`
  in `src/social_support/config.py`. Fields:
  - `database_url: str = "sqlite:///./data/app.db"`
  - `caseworker_passcode: SecretStr | None = None`
  - `assessor: str = "income_rule"`
  - `rule_threshold_aed: Decimal = Decimal("2000")`
  - `rule_band_upper_aed: Decimal = Decimal("2500")`
  - `api_base_url: str = "http://127.0.0.1:8000"`

  Add a validator that rejects `rule_band_upper_aed < rule_threshold_aed`.
- [ ] T007 [P] Write failing unit tests in `tests/unit/test_validation.py`:
  - Emirates ID with dashes, without dashes, or with spaces normalises to `784-YYYY-NNNNNNN-N`.
  - IDs are rejected for a prefix other than `784`, a total length other than 15 digits,
    non-digits, or a year before 1900 or after the current year.
  - `full_name` must be "2–100 chars after trimming".
  - `family_size` must be a "whole number from 1 to 20".
  - Income must be "0–1,000,000 inclusive" with at most 2 decimal places.
  - Each failure returns the field name and the exact message from contracts/api.md.
- [ ] T008 [P] Create pure domain types in `src/social_support/domain/models.py`:
  - String enums:
    - `Outcome` (`APPROVE`, `SOFT_DECLINE`, `NEEDS_HUMAN_REVIEW`; no hard-decline value, per FR-008)
    - `EmploymentStatus` (`EMPLOYED`, `SELF_EMPLOYED`, `UNEMPLOYED`, `STUDENT`, `RETIRED`)
    - `TraceStep` (`RECEIVED`, `VALIDATED`, `ASSESSED`, `STORED`, `RESULT_RETURNED`)
    - `TraceStatus` (`OK`, `FAILED`)
  - Frozen dataclass `ApplicationInput(family_size: int, net_monthly_income_aed: Decimal,
    employment_status: EmploymentStatus)`, with no name or Emirates ID.
  - Frozen dataclass `RuleVersionInfo(id: str, name: str, parameters: dict[str, str])`.
  - Frozen dataclass `AssessmentResult(outcome, income_per_member_aed: Decimal | None,
    explanation: str, suggested_next_steps: tuple[str, ...], flag_reason: str | None,
    rule_version_id: str)`.

    Its `__post_init__` enforces these invariants:
    - The explanation is non-empty.
    - The rule version is non-empty.
    - `SOFT_DECLINE` requires at least 1 next step.
    - `NEEDS_HUMAN_REVIEW` requires a `flag_reason`.
- [ ] T009 Implement `normalise_emirates_id()` and the field validators in
  `src/social_support/domain/validation.py` so that T007 passes. The validators return
  `list[FieldError(field, message)]` and depend on T007 and T008.
- [ ] T010 Define the `Assessor` protocol and the factory in `src/social_support/domain/assessor.py`:
  - The protocol has `rule_version: RuleVersionInfo` and
    `assess(application: ApplicationInput) -> AssessmentResult`.
  - `build_assessor(settings)` maps `"income_rule"` to `IncomePerMemberRuleAssessor` with a lazy
    import, and raises `ValueError` for any unknown name.
  - Also define the constant `FALLBACK_RULE_VERSION = RuleVersionInfo("fallback", "fallback", {})`.
- [ ] T011 [P] Create the SQLAlchemy 2.x ORM models in `src/social_support/persistence/orm.py`,
  using typed `Mapped[]` columns:
  - `applications`:
    - `id` integer PK
    - `reference_number` String(14), unique
    - `full_name` String(100)
    - `emirates_id` String(18), indexed, non-unique
    - `family_size` Integer
    - `net_monthly_income_aed` Numeric(12,2)
    - `employment_status` String
    - `previous_application_exists` Boolean
    - `submitted_at` DateTime(timezone=True)
  - `decisions`:
    - `id`
    - `application_id` FK, unique
    - `outcome` String
    - `income_per_member_aed` Numeric(12,2), nullable
    - `explanation` Text
    - `suggested_next_steps` JSON list
    - `flag_reason` String, nullable
    - `rule_version_id` FK
    - `decided_at` DateTime(timezone=True)
  - `assessment_rule_versions`:
    - `id` String PK
    - `name`
    - `parameters` JSON
    - `created_at`
  - `processing_trace_steps`:
    - `id`
    - `application_id` FK
    - `sequence` Integer
    - `step` String
    - `status` String
    - `detail` String, nullable
    - `occurred_at`

  Store enums as strings, per data-model.md.
- [ ] T012 Implement `src/social_support/persistence/db.py` (depends on T011):
  - `make_engine(url)`. For SQLite, set `check_same_thread=False` and create the parent directory
    of the file.
  - A `sessionmaker`.
  - `init_db(engine)`, which calls `Base.metadata.create_all`.
  - A `get_session` FastAPI dependency.
- [ ] T013 Implement `ApplicationRepository` in `src/social_support/persistence/repository.py`
  with **add and get methods only** (FR-009, R8):
  - `ensure_rule_version(info: RuleVersionInfo)`: insert the row if it is absent; never modify an
    existing row.
  - `add_submission(application, decision, trace_steps)`: one transaction.
  - `add_trace_step(application_id, step)`

  There are no update or delete methods. Depends on T011 and T012.
- [ ] T014 [P] Implement `src/social_support/services/tracing.py`:
  - `configure_logging()`: a JSON formatter on stdlib `logging` that emits only whitelisted
    `extra` keys (`reference_number`, `step`, `status`, `outcome`, `rule_version`, `error_type`).
    It must never emit `emirates_id`, income or name (Principle I).
  - `TraceRecorder`: collects ordered steps (sequence, step, status, detail, UTC `occurred_at`).
- [ ] T015 [P] Implement the `RequestValidationError` handler in `src/social_support/api/errors.py`.
  It returns `422 {"errors": [{"field": ..., "message": ...}]}` with one entry per field: the field
  name is the last element of `loc`, and the message comes from the domain validator when one is
  available.
- [ ] T016 Implement the app factory `create_app(settings: Settings | None = None)` in
  `src/social_support/api/main.py`, with an empty `APIRouter` in `src/social_support/api/routes.py`.
  - The lifespan:
    - calls `configure_logging()`
    - creates the engine and runs `init_db`
    - calls `build_assessor(settings)`
    - calls `ensure_rule_version()` for the assessor's version and for `FALLBACK_RULE_VERSION`
    - stores the engine, sessionmaker, assessor and settings on `app.state`
  - Register the error handler, mount the router at `/api/v1`, and add
    `GET /api/v1/health` returning `{"status": "ok", "assessor": ..., "rule_version": ...}`.
  - Depends on T010 and T012–T015.
- [ ] T017 Create shared fixtures in `tests/conftest.py`:
  - `settings` uses `sqlite://` (in-memory) with `StaticPool` and
    `caseworker_passcode="test-passcode"`.
  - `client` is a `TestClient(create_app(settings))` used as a context manager so the lifespan runs.
  - `FailingAssessor`, whose `assess` raises `RuntimeError`.
  - `make_client(assessor=..., **settings_overrides)`, a factory used to inject fakes.
  - A `db_session` fixture for asserting on stored rows.
- [ ] T018 [P] Create the base `ApiClient` in `src/social_support/ui/client.py`:
  - An `httpx.Client` with `base_url` from the `API_BASE_URL` environment variable and a 10 s
    timeout.
  - A private `_request()` method that maps non-2xx responses to
    `ApiError(status_code, detail, field_errors: dict[str, str])`.
  - It imports nothing from other `social_support` subpackages (R1).
- [ ] T019 [P] Create the Streamlit shell in `src/social_support/ui/app.py`:
  - Page title "Social Support Assessment".
  - `st.tabs(["Apply", "Look up", "Review queue"])`, each tab calling a placeholder
    `render_<tab>(client)` function.
  - A cached `ApiClient` instance.
  - Also create `.streamlit/config.toml` with `[browser]` and `gatherUsageStats = false`, so the UI
    makes no external network calls (plan constraint).

**Checkpoint**: `uv run pytest tests/unit/test_validation.py` passes, and
`GET /api/v1/health` returns 200 with a `rule_version`.

---

## Phase 3: User Story 1 - Submit an application and see a recommendation (Priority: P1) 🎯 MVP

**Goal**: an application is captured, validated and assessed by rule v0.1, and stored with its
decision and trace. The outcome, explanation and reference number are shown immediately.

**Independent Test**: submit valid applications for each outcome band and one invalid application.
Each valid submission shows the predicted outcome with an explanation and a reference number. The
invalid one shows field messages and nothing is stored (quickstart steps 1–5).

### Tests for User Story 1 ⚠️ (write first; they must fail)

- [ ] T020 [P] [US1] Write unit tests for the rule in `tests/unit/test_income_rule.py`:
  - Outcomes at the boundaries:
    - 1999.99 gives `APPROVE`.
    - 2000.00 and 2500.00 give `NEEDS_HUMAN_REVIEW` with `flag_reason == "borderline income"`.
    - 2500.01 gives `SOFT_DECLINE` with at least 1 next step.
    - Income 0 gives `APPROVE`.
  - Income per member is rounded half-up to 2 dp (income 1000, family 3 gives 333.33).
  - The explanation contains the income per member, the threshold or band, the employment status
    and the rule version id.
  - The Needs Human Review explanation contains "caseworker".
  - The rule version id matches `^income-per-member/v0\.1\+[0-9a-f]{8}$`. It stays the same for the
    same parameters and changes when either parameter changes.
- [ ] T021 [P] [US1] Write unit tests for reference numbers in `tests/unit/test_reference.py`.
  Values must match `^SSA-[0-9A-HJKMNP-TV-Z]{10}$` (Crockford base32, no I/L/O/U), and 1,000
  generated values must be unique.
- [ ] T022 [P] [US1] Write contract tests in `tests/contract/test_submit_contract.py` for
  `POST /api/v1/applications`, checking against contracts/api.md:
  - A `201` response has exactly the documented keys.
  - Money values are strings with 2 dp, and there is no internal `id` anywhere in the response.
  - A `422` response has the flat `errors[]` shape, with one entry per invalid field.
  - The app exposes no `PUT`, `PATCH` or `DELETE` route under `/api/v1/applications` (FR-009).
  - A payload containing `nationality` returns 422 with an `errors[]` entry for that field
    (FR-014).
- [ ] T023 [P] [US1] Create the synthetic fixtures in `tests/fixtures/synthetic_applications.py`:
  - `VALID_CASES`: at least 20 entries of `(payload, expected_outcome)` covering all 3 outcomes,
    every boundary value from data-model.md, zero income, family sizes 1 and 20, and all 5
    employment statuses.
  - `INVALID_CASES`: at least one `(payload, expected_error_field)` per validation rule in FR-002.
  - Use only synthetic names and IDs in the `784-YYYY-NNNNNNN-N` format.
- [ ] T024 [US1] Write integration tests in `tests/integration/test_submit_flow.py`, using T017
  and T023:
  - Every `VALID_CASES` entry gets its expected outcome (SC-005).
  - Every `INVALID_CASES` entry returns 422 and leaves zero rows in `applications` (SC-006).
  - Trace steps are stored in the order RECEIVED → VALIDATED → ASSESSED → STORED →
    RESULT_RETURNED, all `OK`.
  - With `FailingAssessor`, the response is `201` with `NEEDS_HUMAN_REVIEW`, `flag_reason`
    "automatic assessment unavailable", rule version `fallback`, the row stored, and the ASSESSED
    step `FAILED` (FR-015).
  - A second submission with the same Emirates ID returns `previous_application_exists: true`,
    its outcome follows the rule only, and the response doesn't contain the first reference
    (FR-017).
  - After changing `rule_threshold_aed`, new decisions use a new rule version while the earlier
    decision keeps its version (FR-013).
  - Logs captured with `caplog` contain the reference number but never the Emirates ID or the
    income value.
  - Submitting all `VALID_CASES` gives a 95th-percentile response time under 5 s (SC-002).
- [ ] T025 [P] [US1] Write a UI smoke test in `tests/ui/test_ui_smoke.py` using
  `streamlit.testing.v1.AppTest` with a monkeypatched `ApiClient`:
  - The Apply tab renders all 5 fields and the income definition help text.
  - Submitting shows the outcome, explanation and reference number.
  - A mocked 422 shows the field messages.

### Implementation for User Story 1

- [ ] T026 [P] [US1] Implement `IncomePerMemberRuleAssessor(threshold_aed, band_upper_aed)` in
  `src/social_support/assessment/income_rule.py`, following data-model.md:
  - `ipm = net_monthly_income_aed / family_size`, rounded with `ROUND_HALF_UP` to 2 dp.
  - The rule version id is `income-per-member/v0.1+` followed by the first 8 hex characters of the
    sha256 of the canonical JSON of the parameters.
  - Outcomes:
    - `ipm < threshold` gives `APPROVE`.
    - `threshold ≤ ipm ≤ band_upper` gives `NEEDS_HUMAN_REVIEW` with "borderline income".
    - `ipm > band_upper` gives `SOFT_DECLINE` with the next steps "Reapply if your household
      income or size changes" and "Ask about economic enablement support (training, job
      matching)".
  - The Approve explanation follows the example in contracts/api.md.
  - The Needs Human Review explanation states the income per member, the band 2000.00–2500.00 AED,
    and that "a caseworker will review this application".
  - The fallback explanation (built in T029) states that automatic assessment was unavailable and
    that a caseworker will review the application.
  - T020 must pass.
- [ ] T027 [P] [US1] Implement `generate_reference()` in `src/social_support/services/reference.py`.
  It returns `"SSA-"` plus 10 Crockford base32 characters built from `secrets.token_bytes`.
  T021 must pass.
- [ ] T028 [US1] Add `emirates_id_has_applications(emirates_id) -> bool` and
  `reference_exists(ref) -> bool` to `src/social_support/persistence/repository.py`.
- [ ] T029 [US1] Implement `ApplicationService.submit(payload)` in
  `src/social_support/services/applications.py`:
  1. Record RECEIVED and VALIDATED.
  2. Run the duplicate check (FR-017).
  3. Call `assessor.assess(ApplicationInput(...))` inside `try`/`except Exception`. On failure,
     build the fallback `AssessmentResult` (R10), record ASSESSED `FAILED` with the exception
     class name as `detail`, and log `error_type`.
  4. Generate the reference, retrying up to 5 times on a unique-constraint collision.
  5. Persist the application, decision and trace in one transaction (STORED).
  6. Write RESULT_RETURNED.
  7. Log `reference_number`, `outcome` and `rule_version` only.

  Return a result DTO. Depends on T026–T028.
- [ ] T030 [US1] Define `SubmitApplicationRequest`, `DecisionOut` and `SubmitApplicationResponse`
  in `src/social_support/api/schemas.py`:
  - Field validators call `domain/validation.py`, so the messages match T007.
  - `emirates_id` is normalised on input.
  - Money is serialised as a string with 2 dp.
  - Timestamps are ISO 8601 UTC.
  - There is no internal `id`.
  - `SubmitApplicationRequest` sets `model_config = ConfigDict(extra="forbid")`, so unknown fields
    such as `nationality` are rejected (FR-014).
- [ ] T031 [US1] Implement the `POST /applications` route in `src/social_support/api/routes.py`.
  It returns `201` with `SubmitApplicationResponse` and gets the service from `app.state` and the
  session dependency. T022 and T024 must pass.
- [ ] T032 [US1] Add `submit(payload) -> dict` to `src/social_support/ui/client.py` and implement
  `render_apply` in `src/social_support/ui/app.py`:
  - A form for name, Emirates ID, family size (1–20), net monthly income (AED) and employment
    status.
  - Income help text: "Net (take-home) monthly income from all sources (salary, business, rental,
    pensions, existing benefits) for all household members".
  - On success, show:
    - the outcome badge (green Approve, amber Needs Human Review, grey Soft Decline)
    - the explanation
    - the next steps
    - the reference number, with a reminder to keep it
    - a note if a previous application exists
  - On `ApiError` 422, show each message under its field. T025 must pass.

**Checkpoint**: US1 is fully working. Quickstart steps 1–5 pass and `uv run pytest` is green.

---

## Phase 4: User Story 2 - Look up a previous application's decision (Priority: P2)

**Goal**: retrieve a stored application and its decision using the reference number and the
matching Emirates ID. Every failure looks identical (Clarification Q1).

**Independent Test**: submit an application, then look it up with the correct ID (with and
without dashes) and get identical details. A wrong ID and an unknown reference both return the
same "not found" (quickstart steps 6–7).

### Tests for User Story 2 ⚠️ (write first; they must fail)

- [ ] T033 [P] [US2] Write contract tests in `tests/contract/test_lookup_contract.py` for
  `POST /api/v1/applications/lookup`:
  - A `200` response has the `application` and `decision` blocks exactly as in contracts/api.md.
  - The `404` body is **byte-identical** for an unknown reference and for a mismatched Emirates ID:
    `{"detail": "No application found for the details provided."}`.
- [ ] T034 [P] [US2] Write integration tests in `tests/integration/test_lookup_flow.py`:
  - Submit, then look up with the dashed and undashed forms of the ID. The decision, explanation,
    rule version and `decided_at` are identical to the submission response (SC-004).
  - A mismatched ID returns 404, and so does an unknown reference.
  - Captured logs and request URLs never contain the Emirates ID.

### Implementation for User Story 2

- [ ] T035 [US2] Add `get_by_reference(ref)` to `src/social_support/persistence/repository.py`. It
  returns the application with its decision and rule version id, or `None`.
- [ ] T036 [US2] Implement `ApplicationService.lookup(reference_number, emirates_id)` in
  `src/social_support/services/applications.py`:
  - Normalise the ID.
  - Return `None` when the reference is unknown **or** the IDs don't match. Compare with
    `secrets.compare_digest`.
  - Log only the reference number and found / not found.
- [ ] T037 [US2] Add `LookupRequest`, `ApplicationOut` and `LookupResponse` to
  `src/social_support/api/schemas.py`. The response reuses `DecisionOut`.
- [ ] T038 [US2] Implement the `POST /applications/lookup` route in
  `src/social_support/api/routes.py`. It returns `200 LookupResponse` or `404` with the single
  constant `NOT_FOUND_DETAIL`. T033 and T034 must pass.
- [ ] T039 [US2] Add `lookup(reference_number, emirates_id)` to `src/social_support/ui/client.py`
  and implement `render_lookup` in `src/social_support/ui/app.py`:
  - Inputs for the reference number and the Emirates ID.
  - Show the submitted details, outcome, explanation, next steps, decision time and rule version.
  - Show "No application found for the details provided." on 404.

**Checkpoint**: US1 and US2 both work independently. Quickstart steps 6–7 pass.

---

## Phase 5: User Story 3 - Caseworker sees applications awaiting human review (Priority: P3)

**Goal**: a passcode-protected list of `NEEDS_HUMAN_REVIEW` applications, newest first
(Clarification Q3).

**Independent Test**: create one borderline and one clear-cut application. With the right
passcode, only the borderline one is listed. With a wrong or missing passcode, access is denied
and no data is shown (quickstart steps 8–9).

### Tests for User Story 3 ⚠️ (write first; they must fail)

- [ ] T040 [P] [US3] Write contract tests in `tests/contract/test_review_queue_contract.py` for
  `GET /api/v1/review-queue`:
  - `401 {"detail": "Access denied."}` when the `X-Caseworker-Passcode` header is missing, when it
    is wrong, and when the server has no passcode configured.
  - A `200` response has `{"items": [{reference_number, full_name, submitted_at, flag_reason}]}`.
- [ ] T041 [P] [US3] Write integration tests in `tests/integration/test_review_queue_flow.py`:
  - With mixed outcomes, only `NEEDS_HUMAN_REVIEW` items are listed, newest first. This includes
    fallback (assessment-failed) cases.
  - With no review cases, the response is `{"items": []}`.
  - When `caseworker_passcode=None`, the response is 401 even if a header is sent (fail closed).

### Implementation for User Story 3

- [ ] T042 [US3] Add `list_needs_review()` to `src/social_support/persistence/repository.py`. It
  joins decisions where the outcome is `NEEDS_HUMAN_REVIEW` and orders by `submitted_at` descending.
- [ ] T043 [US3] Implement the review queue on the API side:
  - Add `ReviewQueueItem` and `ReviewQueueResponse` to `src/social_support/api/schemas.py`.
  - Add the `require_caseworker` dependency in `src/social_support/api/routes.py`. It reads the
    `X-Caseworker-Passcode` header, compares it with `secrets.compare_digest` against
    `settings.caseworker_passcode`, and raises 401 "Access denied." when the header is missing or
    wrong, or no passcode is configured.
  - Add the `GET /review-queue` route.

  T040 and T041 must pass.
- [ ] T044 [US3] Add `review_queue(passcode)` to `src/social_support/ui/client.py` and implement
  `render_review` in `src/social_support/ui/app.py`:
  - A password-type passcode input.
  - A table of reference, name, submitted time and flag reason.
  - The empty-state message "No applications are waiting for review."
  - "Access denied." on 401.

**Checkpoint**: all three stories work independently. Quickstart steps 1–9 pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T045 [P] Write architecture guard tests in `tests/unit/test_architecture.py`:
  - Modules in `social_support.ui` import nothing from the `domain`, `assessment`, `persistence`
    or `services` packages.
  - `social_support.domain` imports neither `sqlalchemy` nor `fastapi`.
  - The `ApplicationInput` fields are exactly `{family_size, net_monthly_income_aed,
    employment_status}`.
- [ ] T046 [P] Write the root `README.md`:
  - Project purpose.
  - Prerequisites (uv; Python 3.12 is fetched automatically).
  - Setup, test and run commands, and the demo script, following
    [quickstart.md](./quickstart.md).
  - A link to the `specs/` folder as the design record.
- [ ] T047 [P] Update `CLAUDE.md`:
  - Replace "No source code exists yet" with the real commands (`uv sync`, `uv run pytest`, how to
    run a single test, ruff, uvicorn and streamlit).
  - Describe the layering: `domain` → `assessment`/`persistence` → `services` → `api`, with `ui`
    talking to the API only, and `Assessor` as the extension point.
- [ ] T048 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`, and fix
  every failure.
- [ ] T049 Run the [quickstart.md](./quickstart.md) manual demo script (steps 1–9) and the FR-013
  rule-change check against the running API and UI. Record any deviations in this file under
  Notes.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (T001–T005)**: no dependencies. T002 needs T001, T003 edits the same file as T001, and
  T005 needs T001–T004.
- **Foundational (T006–T019)**: depends on Setup and **blocks every story**. The internal order is:
  1. T007 and T008, then T009.
  2. T008, then T010.
  3. T011, then T012, then T013.
  4. T010, T012, T013, T014 and T015, then T016.
  5. T016, then T017.
- **US1 (T020–T032)**: depends on Foundational.
- **US2 (T033–T039)**: depends on Foundational. Its tests submit applications through the API, so
  in practice it needs **T029–T031** from US1 to create data.
- **US3 (T040–T044)**: depends on Foundational and, for the same reason, on US1's T029–T031.
- **Polish (T045–T049)**: depends on all the stories you intend to deliver.

### Shared files (no [P] across these, even between stories)

- `src/social_support/persistence/repository.py`: T013, T028, T035, T042
- `src/social_support/services/applications.py`: T029, T036
- `src/social_support/api/schemas.py`: T030, T037, T043
- `src/social_support/api/routes.py`: T016, T031, T038, T043
- `src/social_support/ui/client.py` and `src/social_support/ui/app.py`: T018/T019, T032, T039,
  T044

### Within each story

Write the tests first and confirm they fail, then implement in this order: domain/assessment →
repository → service → schemas → route → UI. Commit at each checkpoint.

---

## Parallel Examples

```text
# Phase 2 — independent files:
T006 config.py   |  T007 test_validation.py  |  T008 domain/models.py
T011 orm.py      |  T014 tracing.py          |  T015 api/errors.py
T018 ui/client.py|  T019 ui/app.py

# US1 — tests together, then the two pure units together:
T020 test_income_rule.py | T021 test_reference.py | T022 test_submit_contract.py
T023 synthetic fixtures  | T025 test_ui_smoke.py
then: T026 income_rule.py | T027 reference.py

# US2 / US3 tests can be written in parallel with each other:
T033 | T034 | T040 | T041
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1, then Phase 2, then Phase 3 (US1).
2. **Stop and validate**: run quickstart steps 1–5 and `uv run pytest`.
3. Commit with the message "feat(001): US1 submit & recommend". This alone proves the end-to-end
   path.

### Incremental delivery

1. Add US2 (lookup), validate steps 6–7, and commit.
2. Add US3 (review queue), validate steps 8–9, and commit.
3. Polish, then run the full quickstart, then `/speckit-converge` to confirm nothing was missed.

---

## Notes

- `[P]` means a different file with no dependency on an incomplete task.
- Every task ID maps back to an FR, an SC or a research decision, so `/speckit-analyze` can check
  coverage.
- Use synthetic data only (Constitution I). Never put real Emirates IDs in fixtures.
