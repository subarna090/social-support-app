# Research: Application Walking Skeleton

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-10-23

The user fixed the core stack: Python 3.12 with uv, FastAPI, Streamlit, SQLite through SQLAlchemy,
and pytest. This document resolves the remaining design decisions. There were no open
NEEDS CLARIFICATION items in the Technical Context.

---

## R1. How the UI talks to the system

- **Decision**: Streamlit is a thin client that calls the FastAPI service over HTTP using `httpx`.
  The UI never imports persistence or assessment code.
- **Rationale**: Principle VI requires swappable infrastructure, and the brief requires API design
  for integration. Keeping a clean API boundary from day 1 means later features (chat, agents)
  and external systems use the same contract. It also lets API tests cover all business behaviour,
  so UI tests can stay minimal.
- **Alternatives considered**: Streamlit calling services in-process (simpler, one process) was
  rejected because it would merge UI and domain code and hide the API contract.

## R2. Assessment interface (the extension point for the ML and agent versions)

- **Decision**: define an `Assessor` protocol in the domain layer:
  `assess(application: ApplicationInput) -> AssessmentResult`. `AssessmentResult` carries the
  outcome, explanation, income per member, suggested next steps, flag reason, and rule version.
  `IncomePerMemberRuleAssessor` (v0.1) is the only implementation in this slice. It is chosen by a
  configuration key (`ASSESSOR=income_rule`) and wired up through a small factory.
- **Rationale**: the user asked for the assessment to sit behind an interface. Features 005
  (scikit-learn) and 006 (LangGraph agents) add new `Assessor` implementations without touching
  the API, the persistence layer, or the UI. Because `AssessmentResult` already includes the
  explanation and rule version, Principle II holds for every future implementation.
- **Alternatives considered**: an abstract base class (works, but a Protocol is lighter and easier
  to fake in tests); a plugin or entry-point system (more than this PoC needs, per Principle VIII).

## R3. Rule versioning (FR-013)

- **Decision**: the rule parameters (`threshold_aed`, `band_upper_aed`) come from settings. At
  startup the system computes a version id `income-per-member/v0.1+<sha256(params)[:8]>` and
  inserts an `AssessmentRuleVersion` row if one doesn't already exist. Every decision references
  that row.
- **Rationale**: changing the parameters automatically produces a new, distinct version with no
  manual bookkeeping, and old decisions keep pointing at the version that was actually applied
  (Principle IV: decisions can be replayed).
- **Alternatives considered**: a manually bumped version string, rejected because it's easy to
  forget and silently breaks auditability.

## R4. Reference numbers (FR-004)

- **Decision**: the format is `SSA-` followed by 10 characters of Crockford base32 from
  `secrets.token_bytes` (about 50 bits), for example `SSA-7K2M9QXH4D`. Uniqueness is enforced by a
  unique constraint, with a retry if a collision ever happens.
- **Rationale**: not guessable or sequential (spec assumption), readable aloud, and free of
  ambiguous characters (no I, L, O, U).
- **Alternatives considered**: UUID4 (secure but long and awkward for a person to type); a
  sequential id (reveals how many applications exist).

## R5. Emirates ID validation and normalisation

- **Decision**: accept 15 digits with or without dashes, in the pattern
  `784-YYYY-NNNNNNN-N`. Strip spaces and dashes, then store the canonical dashed form
  `784-YYYY-NNNNNNN-N`. Validate the prefix `784`, a 4-digit year between 1900 and the current year,
  and the total length. Check-digit (Luhn) validation is **deferred** to feature 002, where the
  synthetic data generator will produce valid check digits.
- **Rationale**: matches FR-002 as specified (format only). Adding the checksum now would reject
  hand-typed demo IDs.
- **Alternatives considered**: Luhn validation now, deferred as explained above.

## R6. Secure lookup (FR-011, Clarification Q1)

- **Decision**: `POST /api/v1/applications/lookup` with a JSON body
  `{reference_number, emirates_id}`. A non-existent reference and a mismatched ID both return the
  same `404` body. The Emirates ID is compared after normalisation.
- **Rationale**: using POST keeps the Emirates ID out of URLs, server access logs and browser
  history. The identical 404 prevents anyone from probing which references exist.
- **Alternatives considered**: `GET /applications/{ref}?emirates_id=…`, rejected because the ID
  would leak into logs and history.

## R7. Caseworker passcode (FR-012, Clarification Q3)

- **Decision**: the passcode is read from the `CASEWORKER_PASSCODE` environment variable (or a
  `.env` file through pydantic-settings) and sent in the `X-Caseworker-Passcode` header. It is
  compared with `secrets.compare_digest`. A missing or wrong passcode returns `401` with no data.
  If no passcode is configured, the review endpoint always returns `401` (fail closed).
- **Rationale**: this is the simplest mechanism that satisfies the clarification, avoids timing
  attacks, and gives later authentication a single place to plug in (a FastAPI dependency).
- **Alternatives considered**: HTTP Basic auth (adds a username with no meaning here); a session
  cookie (the UI is a separate process, so it adds complexity for no gain).

## R8. Immutability of decisions (FR-009)

- **Decision**: the API exposes no update or delete operations for applications or decisions,
  and the repository interface has only `add` and `get` methods. A test asserts that no
  PUT/PATCH/DELETE routes exist on these resources.
- **Rationale**: enforcing immutability in code is enough for a single-user PoC. Database-level
  enforcement (triggers, or revoking UPDATE on Postgres) is recorded as a hardening step for
  production.
- **Alternatives considered**: SQLite triggers, deferred because they aren't portable to Postgres
  as written and complicate testing.

## R9. Processing trace and observability (FR-016, Principle VII)

- **Decision**:
  - Each request records `ProcessingTraceStep` rows (`received`, `validated`, `assessed`, `stored`,
    `result_returned`), each with a timestamp, status and optional detail, linked to the
    application.
  - Steps are collected in memory during the request. `received`, `validated` and `assessed` are
    written in the same transaction as the application; `result_returned` is written just before
    the response is sent.
  - In addition, the system writes structured JSON logs (stdlib `logging` with a JSON formatter)
    that include the reference number and **exclude** the Emirates ID and income.
- **Interpretation**: FR-016's "result returned to the user" step is recorded as `RESULT_RETURNED`.
  The server can't observe the browser actually rendering the result, so the step marks the
  response being sent.
- **Rationale**: there are no LLM or agent calls in this slice, so Langfuse adds nothing yet. The
  trace table satisfies "reconstructible processing path" now, and Langfuse is added in feature
  008, wrapping the `Assessor` call.
- **Alternatives considered**: Langfuse now, rejected because there's nothing to trace that the
  table doesn't already cover, and the self-hosted version needs Docker, which this machine
  doesn't have. OpenTelemetry is reconsidered in feature 008.

## R10. Assessment failure routing (FR-015)

- **Decision**: the application service wraps `assessor.assess()`. On any exception it builds a
  fallback `AssessmentResult` with outcome `NEEDS_HUMAN_REVIEW`, flag reason
  `automatic assessment unavailable`, and rule version `fallback`, logs the error with the
  reference number, and stores the application as normal.
- **Rationale**: Principle III (never leave an applicant with an error instead of an outcome)
  together with the spec edge case.

## R11. Persistence: schema management and portability

- **Decision**:
  - SQLAlchemy 2.x ORM, using typed `Mapped[]` models.
  - The database URL comes from settings (default `sqlite:///./data/app.db`).
  - Tables are created with `Base.metadata.create_all` at startup.
  - Money is stored as `Numeric(12, 2)` and handled as `Decimal`.
  - Timestamps are timezone-aware UTC.
  - Enums are stored as strings.
- **Rationale**: these choices run unchanged on SQLite and PostgreSQL (Principle VI). Alembic is
  deferred: one schema with no production data doesn't justify migrations yet (Principle VIII).
  Alembic is introduced the first time the schema changes, which is expected in feature 003.
- **Alternatives considered**: SQLModel (fewer models, but mixing API and ORM models makes the
  boundary harder to see); Alembic from day 1 (deferred, as above).

## R12. Testing approach

- **Decision**:
  - Unit tests: validation, Emirates ID normalisation, rule assessor boundaries (1999.99,
    2000.00, 2500.00, 2500.01), reference number generation.
  - Contract tests: FastAPI `TestClient` against each endpoint in
    [contracts/api.md](./contracts/api.md), covering status codes and response shapes.
  - Integration tests: the full path against an in-memory SQLite database (`StaticPool`),
    including assessor failure (a fake `Assessor` that raises) and duplicate detection.
  - UI: a smoke test with `streamlit.testing.v1.AppTest`, with the API client mocked.
  - Test-first for validation and assessment (Principle V).
  - A synthetic fixture set of at least 20 applications covering all three outcomes, for SC-005.
- **Tooling**: `pytest`, `ruff` for linting and formatting, run with `uv run`.

## R13. Duplicate detection (FR-017, Clarification Q2)

- **Decision**: before storing, check whether any application exists with the same normalised
  Emirates ID. If so, set `previous_application_exists = true` on the new application, which the
  response and UI show as a note. Nothing about the earlier application is returned. There is a
  non-unique index on `emirates_id`.
- **Rationale**: this follows the clarification exactly: the outcome is unaffected and nothing
  leaks.
