# Implementation Plan: Synthetic Applicant Data Generator

**Branch**: `002-synthetic-data-generator` | **Date**: 2026-10-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-synthetic-data-generator/spec.md`

## Summary

Build a terminal command that generates reproducible, clearly synthetic applicant packs. Each pack
has the form details, five readable documents (bank statement, Emirates ID card image, resume,
assets and liabilities spreadsheet, credit report) and an answer key. The command can inject one
recorded cross-document inconsistency into a chosen share of packs, export a labelled summary
table with a controllable outcome mix, and seed the running 001 application through its normal
submission endpoint.

Labels come from a versioned, data-driven labelling policy: an ordered list of named rules, first
match wins, over income per member, employment history, net wealth and credit standing. It lives in
its own pure `labelling` package so the ML feature (005) can reuse it. Every pack carries two
labels: the **eligibility outcome** from its true facts, and the **expected routing**, which is
Needs Human Review when an inconsistency was injected.

## Technical Context

**Language/Version**: Python 3.12, managed by `uv`. This extends the existing `social_support`
package.

**Primary Dependencies**:
- New runtime: `faker` (identities), `reportlab` (PDFs), `openpyxl` (xlsx)
- Promoted to direct runtime dependencies (already installed through Streamlit): `pillow` (ID card
  image), `pandas` (summary table)
- Reused: `httpx` through `ui.client.ApiClient` (seeding); standard-library `tomllib`, `argparse`,
  `random`, `hashlib`
- New dev dependency: `pypdf` (tests read PDF text back)

**Storage**: files only, under `data/synthetic/<run-id>/` (git-ignored). No database changes.

**Testing**: pytest. Unit tests (policy, ID generator, allocation, injection, sampler), integration
tests (generate into `tmp_path` and check documents against answer keys, determinism, CLI errors),
and an end-to-end test (generate, seed the 001 app in-process, look up). A `slow` marker is used for
the SC-001 timing test and the 200-pack SC-003 and SC-004 checks.

**Target Platform**: the local Windows 11 laptop (CPU only, about 15 GB RAM, no Docker). Works
offline.

**Project Type**: CLI tool plus a reusable library package inside the existing single Python
project.

**Performance Goals**: 100 complete packs in under 5 minutes (SC-001); the expected time is well
under 1 minute (each PDF takes tens of milliseconds to render). Batches of up to 5,000 packs.

**Constraints**: deterministic for a given count, seed, settings and as-of date. No real
organisation branding. Console output and logs carry no names, IDs or incomes. Nothing is written
unless all arguments are valid.

**Scale/Scope**: 1 CLI with 2 subcommands, 5 document renderers, 5 inconsistency types, 1 policy
file with 8 rules, up to 5,000 packs per run.

No NEEDS CLARIFICATION items remain. The user fixed the libraries, the policy location and the
output folder, and the other choices are resolved in [research.md](./research.md) (R1–R14).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Pre-research | Post-design | Evidence |
|---|---|---|---|
| I. Local-first & privacy | PASS | PASS | No LLM or network use during generation; seeding targets only the local API. All data is fictional, using a reserved Emirates ID block, the `example.com` domain and invented organisations (R6). Output is git-ignored (R9). The console prints no personal data (contracts/cli.md) |
| II. Explainable decisions | PASS | PASS | Every label names the rule that fired, the values compared and a reason (R2, R3, data-model LabelResult). Answer keys trace every document value (FR-005) |
| III. Human-in-the-loop | PASS | PASS | Packs with inconsistencies have the expected routing Needs Human Review (FR-011). Policy v1 has no hard decline; borderline income, credit problems and unstable work go to review (R3). Thresholds are data in the policy file, not code |
| IV. Fairness & auditability | PASS | PASS | `HouseholdFacts` excludes protected attributes and identity, and a test asserts its exact field set. Nationality and gender appear only as `audit_` columns, so feature 005 can produce the outcome-by-group evaluation report the principle requires (R10). Every run records the generator and policy versions (FR-015) |
| V. Test-first for decision logic | PASS | PASS | The labelling evaluator and policy v1 are written test-first, with boundary tests for every rule (R14). The end-to-end test runs over synthetic data (generate, seed, look up) |
| VI. Swappable infrastructure | PASS | PASS | The policy is a versioned data file loaded through a small interface (`load_policy`, `evaluate`). The generator's settings are CLI options with documented defaults, and seeding uses `API_BASE_URL` from the environment or `.env`. No vendor SDKs in business logic: `labelling` imports only `domain` |
| VII. End-to-end observability | PASS (partial, justified) | PASS (partial, justified) | `run.json` is the audit record of each run, and seeding writes a per-pack report. CLI logs go through the existing JSON formatter with whitelisted keys. There are still no agent or LLM calls to trace (Langfuse comes in feature 008), carried over from 001's Complexity Tracking |
| VIII. Simplicity & thin slices | PASS | PASS | One CLI built with argparse, no new service and no UI or API changes (FR-021). Each user story can be demonstrated alone: generate, then inject, then export, then seed. Scan effects and Arabic text are deferred (spec Assumptions). The new dependencies are the ones the user named |
| Constraint: generators MUST produce deliberate cross-document inconsistencies | PASS | PASS | Five recorded types with exact counts (R8, FR-007–FR-009) |

**Gate result: PASS.** Principle VII is still partial for the same reason as in 001; see
Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-synthetic-data-generator/
├── spec.md                    # Feature spec (clarified, 4 Q&As)
├── plan.md                    # This file
├── research.md                # Phase 0: decisions R1–R14
├── data-model.md              # Phase 1: entities
├── quickstart.md              # Phase 1: validation guide
├── contracts/
│   ├── cli.md                 # social-support-data generate / seed
│   ├── pack-format.md         # run folder, form.json, answer_key.json, summary.csv, run.json
│   └── labelling-policy.md    # policy TOML format, validation, evaluation
├── checklists/
│   └── requirements.md        # Spec quality checklist (16/16)
└── tasks.md                   # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
pyproject.toml                         # + faker, reportlab, openpyxl, pillow, pandas; dev: pypdf;
                                       #   [project.scripts] social-support-data; pytest "slow" marker

src/social_support/
├── labelling/                         # NEW, pure, reused by feature 005
│   ├── __init__.py                    # load_policy, HouseholdFacts, LabelResult
│   ├── facts.py                       # HouseholdFacts (no identity, no protected attributes)
│   ├── policy.py                      # TOML loader + validation, version id, evaluate()
│   └── policies/
│       └── eligibility_v1.toml        # 8 ordered rules (research R3)
└── synthetic/                         # NEW
    ├── __init__.py                    # GENERATOR_VERSION
    ├── __main__.py                    # python -m social_support.synthetic
    ├── cli.py                         # argparse: generate, seed; argument checks
    ├── identities.py                  # names, reserved-block Emirates IDs (Luhn), addresses, contacts
    ├── profile.py                     # HouseholdProfile, outcome-targeted sampler, to_facts()
    ├── allocation.py                  # largest-remainder quotas, slot assignment
    ├── inconsistencies.py             # 5 types: applicability + injection
    ├── pack.py                        # ApplicantPack, form + answer key serialisation
    ├── documents/
    │   ├── common.py                  # synthetic marking, money and date formatting
    │   ├── bank_statement.py          # reportlab
    │   ├── resume.py                  # reportlab
    │   ├── credit_report.py           # reportlab
    │   ├── emirates_id.py             # Pillow
    │   └── assets_liabilities.py      # openpyxl
    ├── run.py                         # GenerationRequest validation, run id, temp folder + rename, run.json
    ├── dataset.py                     # summary.csv with pandas
    ├── seeding.py                     # submit via ui.client.ApiClient, seeding_report.csv
    └── data/
        └── names.toml                 # curated Arabic names (English letters), districts, streets, employers

tests/
├── unit/
│   ├── test_labelling_policy.py       # test-first: every rule boundary, order, default, invalid files
│   ├── test_identities.py             # ID format, Luhn, reserved block, accepted by domain.validation
│   ├── test_allocation.py             # largest remainder, rounding never more than 1 per outcome
│   ├── test_inconsistencies.py        # applicability, exact counts, altered differs from true
│   ├── test_profile_sampler.py        # 500 profiles meet the mix (SC-005); invariants
│   └── test_architecture.py           # + labelling and synthetic import rules; HouseholdFacts fields
├── integration/
│   ├── test_generate_batch.py         # documents vs answer key (SC-003/004), marking (SC-006)
│   ├── test_determinism.py            # SC-002
│   ├── pack_checks.py                 # reusable document-vs-answer-key checker
│   ├── test_large_batch.py            # @slow: 200-pack SC-003 / SC-004 checks
│   ├── test_dataset.py                # summary.csv columns, labels, outcome counts
│   ├── test_cli.py                    # argument errors write nothing; overwrite protection
│   ├── test_seeding.py                # in-process 001 app; unreachable API; 422 recorded
│   └── test_generation_speed.py       # @slow: 100 packs in under 5 minutes (SC-001)
└── e2e/
    └── test_generate_seed_lookup.py   # generate 20, seed, look up 3 (Principle V)
```

**Structure Decision**: two new subpackages inside the existing `src/social_support` package,
following 001's layering. `labelling` sits beside `domain` as a pure, inner layer (it imports only
`domain`). `synthetic` is an outer tool layer: it may import `domain`, `labelling`, `ui.client`
and `services.tracing`, and nothing that touches storage or the API's internals. Its only path into
the application is HTTP (R1, R11). Architecture tests enforce both rules.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Principle VII still partial: no Langfuse or agent tracing | There are no agent or LLM calls in this feature either; Langfuse is planned for feature 008 | The run record, seeding report and JSON logs capture everything this feature does |
| `synthetic` imports `ui.client` (an outer layer importing a sibling outer layer) | Seeding must use the existing submission path with the same `API_BASE_URL` handling (FR-021, R11) | A second HTTP client would duplicate configuration and error handling; calling `ApplicationService` directly would bypass the submission path. If more tools need the client, it can move to a shared `social_support/client` package |
