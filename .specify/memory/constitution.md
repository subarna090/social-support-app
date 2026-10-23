# Social Support AI Assessor Constitution

## Core Principles

### I. Local-First & Data Privacy

- All LLM and ML inference MUST run on locally hosted models (Ollama). No hosted LLM APIs may be
  called with applicant data.
- Applicant data (forms, documents, extracted fields, decisions) MUST NOT leave the local machine.
- The PoC MUST use synthetic or mock data only. Real personal data is prohibited.
- Any optional external service (e.g. a hosted observability tier) MUST receive synthetic data only,
  and its use MUST be recorded as a trade-off in the plan.

Rationale: a government social-support workflow handles highly sensitive personal and financial
data, and data residency is a baseline public-sector expectation.

### II. Explainable Decisions

- Every recommendation (approve or soft decline, plus enablement suggestions) MUST include a
  human-readable rationale that cites the eligibility rules, model features, and source documents
  that drove it.
- Opaque outcomes (a label without its reasons) are a defect.
- Extracted values used in a decision MUST be traceable to the document they came from.

Rationale: applicants and caseworkers must be able to understand and contest decisions.

### III. Human-in-the-Loop

- Cases with low model confidence, unresolved cross-document conflicts, or failed extraction MUST
  be routed to a human reviewer rather than auto-decided.
- The system MUST NOT issue a final hard decline automatically. "Soft decline" is the most
  negative automated outcome, and it always comes with next steps.
- Confidence thresholds for routing MUST be explicit, configurable values.

Rationale: automation targets speed, but accountability for adverse outcomes stays with people.

### IV. Fairness & Auditability

- Protected attributes (nationality, gender, religion, ethnicity, marital status as such) MUST NOT
  be used as model input features. They may be stored only where operationally required.
- Every decision MUST be persisted with its inputs, model version, rule version, and rationale so
  it can be replayed and audited.
- The eligibility model MUST be accompanied by an evaluation report covering accuracy and outcome
  rates across relevant groups.

Rationale: the brief cites subjective, biased decisions as a core pain point. The system must
reduce bias, not automate it.

### V. Test-First for Decision Logic

- Validation, reconciliation, and eligibility logic MUST be developed test-first: tests written and
  failing before implementation.
- Agents MUST be testable with a mocked LLM so their control flow is verifiable without a running
  model.
- Each feature MUST ship with at least one end-to-end test over synthetic data.

Rationale: decision correctness matters more than speed of delivery, and LLM non-determinism must
be isolated from logic that can be tested.

### VI. Swappable Infrastructure

- Storage (relational and vector) and model providers MUST sit behind interfaces so that
  implementations can be swapped through configuration (e.g. SQLite → PostgreSQL, one Ollama model
  → another).
- Business logic MUST NOT import vendor SDKs directly. It depends on project-level abstractions.
- Configuration MUST come from environment variables or config files, never hard-coded values.

Rationale: the PoC runs on a laptop but must show a credible path to production infrastructure.

### VII. End-to-End Observability

- Every agent step, tool call, and LLM call MUST be traced with inputs, outputs, latency, and the
  application ID.
- Logs MUST be structured and MUST NOT contain secrets.
- A single application's full processing path MUST be reconstructible from its traces.

Rationale: agentic systems are hard to debug, and auditability (Principle IV) depends on traces.

### VIII. Simplicity & Thin Vertical Slices

- Work MUST be delivered as thin, end-to-end vertical slices, each one demonstrable on its own.
- Each slice MUST stay within PoC scope. Speculative scaling, multi-tenancy, and premature
  optimisation are out of scope unless a spec requires them.
- Any added complexity (new service, new framework, extra abstraction layer) MUST be justified in
  the plan's Complexity Tracking section.

Rationale: a time-boxed PoC succeeds by showing a working end-to-end flow early and then deepening
it.

## Technology & Data Constraints

- Language: Python. Environments and dependencies are managed with `uv`.
- Target runtime: a single Windows laptop, CPU only, about 15 GB RAM, no Docker. Designs MUST run
  within these limits, and model choices MUST be sized accordingly.
- Required capability classes (the specific tools are chosen in each plan): local LLM hosting,
  agent orchestration with a named reasoning pattern, a scikit-learn classifier with documented
  justification, multimodal ingestion (text, images, tabular), a relational store, a vector store,
  an API layer, a chat-capable demo UI, and tracing.
- Synthetic data generators MUST produce deliberate cross-document inconsistencies so that
  validation can be exercised.

## Development Workflow & Quality Gates

- Every feature follows the Spec Kit flow: specify → clarify → plan → tasks → analyze → implement.
- `spec.md` describes what and why only. Technology choices appear in `plan.md` and nowhere earlier.
- Every plan MUST pass a Constitution Check against Principles I–VIII before research and again
  after design. Violations MUST be recorded and justified in Complexity Tracking, or the plan
  changed.
- `/speckit-analyze` MUST report no CRITICAL issues before `/speckit-implement` runs.
- A feature is done when its tests pass, its end-to-end demo path works on synthetic data, and the
  README and CLAUDE.md reflect any new run commands.

## Governance

- This constitution supersedes ad-hoc practices. Where a spec, plan, or task conflicts with it, the
  constitution wins until it is amended.
- Amendments are made through `/speckit-constitution`, with a Sync Impact Report and a version bump:
  MAJOR for removing or redefining a principle, MINOR for adding a principle or materially expanding
  one, PATCH for clarifications.
- Every plan's Constitution Check and every `/speckit-analyze` run constitutes the compliance
  review.
- Runtime development guidance for coding agents lives in `CLAUDE.md`.

**Version**: 1.0.0 | **Ratified**: 2026-10-23 | **Last Amended**: 2026-10-23
