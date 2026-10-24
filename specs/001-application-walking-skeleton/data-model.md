# Data Model: Application Walking Skeleton

**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Storage is relational: SQLite now and PostgreSQL later, using the same models (Principle VI). All
records are **append-only**: there are no update or delete operations (FR-009). Timestamps are
timezone-aware UTC.

## Entity relationships

```text
AssessmentRuleVersion 1 ──< Decision >── 1 Application 1 ──< ProcessingTraceStep
```

- An Application has exactly **one** Decision in this feature.
- A Decision references the **one** AssessmentRuleVersion it was made with. The special fallback
  version is used when assessment fails.
- An Application has **many** ProcessingTraceSteps, in order.

---

## Application

| Field | Type | Rules |
|---|---|---|
| `id` | integer, PK | Internal only, never exposed |
| `reference_number` | string(14), unique | `SSA-` + 10 Crockford base32 chars (R4) |
| `full_name` | string(100) | 2–100 chars after trimming (FR-002) |
| `emirates_id` | string(18), indexed (non-unique) | Normalised `784-YYYY-NNNNNNN-N` (R5) |
| `family_size` | integer | 1–20 inclusive |
| `net_monthly_income_aed` | decimal(12,2) | 0–1,000,000 inclusive; net, all sources, all members (Clarification Q4) |
| `employment_status` | enum string | `EMPLOYED`, `SELF_EMPLOYED`, `UNEMPLOYED`, `STUDENT`, `RETIRED` |
| `previous_application_exists` | boolean | True if another application with the same `emirates_id` existed when this one was submitted (FR-017) |
| `submitted_at` | timestamp (UTC) | Set by the server |

Protected attributes (nationality, gender, religion, ethnicity) are deliberately **absent**
(FR-014).

## Decision

| Field | Type | Rules |
|---|---|---|
| `id` | integer, PK | Internal |
| `application_id` | FK → Application, unique | One decision per application |
| `outcome` | enum string | `APPROVE`, `SOFT_DECLINE`, `NEEDS_HUMAN_REVIEW`. There is no hard decline value (FR-008) |
| `income_per_member_aed` | decimal(12,2), nullable | `net_monthly_income_aed / family_size`, rounded half-up to 2 dp. Null only for the fallback |
| `explanation` | text | Plain language. Must state the inputs, the income per member, the threshold or band, and the rule version (FR-006) |
| `suggested_next_steps` | JSON list of strings | At least 1 item when outcome is `SOFT_DECLINE` (FR-007) |
| `flag_reason` | string, nullable | Required when outcome is `NEEDS_HUMAN_REVIEW` (e.g. "borderline income", "automatic assessment unavailable") |
| `rule_version_id` | FK → AssessmentRuleVersion | |
| `decided_at` | timestamp (UTC) | Set by the server |

## AssessmentRuleVersion

| Field | Type | Rules |
|---|---|---|
| `id` | string, PK | `income-per-member/v0.1+<sha8>`, or `fallback` (R3) |
| `name` | string | e.g. `income-per-member` |
| `parameters` | JSON | e.g. `{"threshold_aed": "2000.00", "band_upper_aed": "2500.00"}` |
| `created_at` | timestamp (UTC) | |

A row is inserted at startup if the configured parameters produce a new id. Existing rows are
never modified.

## ProcessingTraceStep

| Field | Type | Rules |
|---|---|---|
| `id` | integer, PK | |
| `application_id` | FK → Application | |
| `sequence` | integer | 1..n, in order |
| `step` | enum string | `RECEIVED`, `VALIDATED`, `ASSESSED`, `STORED`, `RESULT_RETURNED` |
| `status` | enum string | `OK`, `FAILED` |
| `detail` | string, nullable | e.g. an exception class name on assessment failure. Never contains the Emirates ID or income |
| `occurred_at` | timestamp (UTC) | |

Invalid submissions are rejected before an Application exists, so they produce no trace rows.
They are recorded only in structured logs, without the submitted values.

---

## Assessment rule v0.1: decision logic

Let `ipm = net_monthly_income_aed / family_size` (Decimal, rounded half-up to 2 dp).

| Condition | Outcome | `flag_reason` | Next steps |
|---|---|---|---|
| `ipm < threshold_aed` (default 2,000) | `APPROVE` | none | none |
| `threshold_aed ≤ ipm ≤ band_upper_aed` (default 2,500) | `NEEDS_HUMAN_REVIEW` | `borderline income` | none |
| `ipm > band_upper_aed` | `SOFT_DECLINE` | none | at least 1, e.g. "Reapply if your household income or size changes", "Ask about economic enablement support (training, job matching)" |
| Assessor raises an exception | `NEEDS_HUMAN_REVIEW` | `automatic assessment unavailable` | none |

Boundary test values: 1999.99 gives Approve, 2000.00 and 2500.00 give Needs Human Review, and
2500.01 gives Soft Decline.

## Domain types (not persisted)

- **ApplicationInput**: the validated submission passed to the `Assessor`. It contains only
  `family_size`, `net_monthly_income_aed` and `employment_status`, with no name or Emirates ID, so
  assessors can't depend on identity.
- **AssessmentResult**: `outcome`, `income_per_member_aed`, `explanation`,
  `suggested_next_steps`, `flag_reason`, `rule_version_id`. This is what every `Assessor` returns
  (R2).
