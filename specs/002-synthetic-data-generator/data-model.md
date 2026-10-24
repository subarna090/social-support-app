# Data Model: Synthetic Applicant Data Generator

All entities are in-memory Python types that are written to files. This feature adds no database
tables. Money is `Decimal` with 2 decimal places and is written to JSON as a string, as in feature
001. Dates are ISO `YYYY-MM-DD`.

---

## HouseholdFacts (`labelling/facts.py`)

The only input the labelling policy sees. Frozen dataclass. It contains **no protected attributes
and no identity**; an architecture test asserts the exact field set, as for `ApplicationInput` in
001.

| Field | Type | Derived from |
|---|---|---|
| `family_size` | int ≥ 1 | number of household members including the applicant |
| `net_monthly_income_aed` | Decimal ≥ 0 | sum of all monthly income sources |
| `income_per_member_aed` | Decimal | `net_monthly_income_aed / family_size`, ROUND_HALF_UP to 2 dp |
| `employment_status` | `domain.models.EmploymentStatus` | profile |
| `months_employed_last_24` | int 0–24 | months covered by jobs in the 24 months before the as-of date |
| `total_assets_aed` | Decimal ≥ 0 | sum of asset values |
| `total_liabilities_aed` | Decimal ≥ 0 | sum of outstanding liability balances |
| `net_wealth_aed` | Decimal | assets minus liabilities (may be negative) |
| `credit_score` | int 300–900 | credit report |
| `active_credit_defaults` | int ≥ 0 | credit report |

Factor names in the policy file must be field names of this type; the loader rejects anything else.

## LabellingPolicy and LabelResult (`labelling/policy.py`)

- **Condition**: `factor` (a HouseholdFacts field), `op` (`lt`, `le`, `gt`, `ge`, `eq`, `in`),
  `value` (a number, or a list of strings for `in`).
- **Rule**: `id` (snake_case, unique in the policy), `outcome` (`domain.models.Outcome`),
  `conditions` (a list; all must hold; empty only for the last rule), `reason` (a template using
  `{factor}` placeholders).
- **LabellingPolicy**: `name` (`eligibility`), `version` (`v1`), `version_id`
  (`eligibility/v1+<sha256[:8]>`), `rules` (an ordered tuple).

  Validation on load: at least one rule; unique ids; known factors and operators; the last rule
  has no conditions and no other rule lacks them; the outcome is a valid `Outcome`.
- **LabelResult**: `outcome`, `rule_id`, `compared` (a dict mapping each factor the rule tested to
  the household's value), `reason` (the rendered template), `policy_version_id`.

`evaluate(facts) -> LabelResult` goes through the rules in order and returns the first match. It is
pure and deterministic.

## HouseholdProfile (`synthetic/profile.py`)

The true facts about one fictional household. Every document is rendered from it.

| Group | Fields |
|---|---|
| Identity | `full_name`, `emirates_id`, `date_of_birth`, `nationality`\*, `gender`\* |
| Contact | `address` (`unit`, `street`, `district`, `emirate`), `email`, `phone` |
| Household | `members`: a list of `{name, relationship (SPOUSE, CHILD, PARENT, SIBLING), age}`; the applicant is not in the list; `family_size = 1 + len(members)` |
| Employment | `employment_status`; `jobs`: a list of `{employer, title, start (month), end (month or null for current)}` |
| Income | `income_sources`: a list of `{kind (SALARY, BUSINESS, RENTAL, PENSION, BENEFIT), monthly_amount_aed, payer}` |
| Wealth | `assets`: a list of `{kind (CASH, PROPERTY, VEHICLE, INVESTMENT), description, value_aed}`; `liabilities`: a list of `{kind (MORTGAGE, CAR_LOAN, PERSONAL_LOAN, CREDIT_CARD), lender, outstanding_aed, monthly_payment_aed}` |
| Credit | `credit_score`, `active_credit_defaults`, `credit_accounts`: a list of `{lender, kind, balance_aed, status (CURRENT, LATE, DEFAULT)}` |

\* Protected attributes: used only to make documents realistic and to fill the `audit_` columns.
They are never passed to `HouseholdFacts`.

Invariants:
- `active_credit_defaults` equals the number of accounts with status `DEFAULT`.
- The employment status is consistent with the jobs: EMPLOYED or SELF_EMPLOYED means there is a
  current job; any other status means there is none.
- If the income includes a SALARY source, its payer is the current employer.

`to_facts(profile, as_of) -> HouseholdFacts` is the single place where the facts are derived.

## Inconsistency (`synthetic/inconsistencies.py`)

| Field | Type | Notes |
|---|---|---|
| `type` | enum | `INCOME_MISMATCH`, `ADDRESS_MISMATCH`, `FAMILY_SIZE_MISMATCH`, `IDENTITY_MISMATCH`, `EMPLOYMENT_MISMATCH` |
| `documents` | list[str] | the two places that disagree, e.g. `["form", "bank_statement"]` |
| `field` | str | e.g. `net_monthly_income_aed`, `address`, `full_name` |
| `true_value` | str | rendered as a string |
| `altered_value` | str | rendered as a string; always differs from `true_value` |

Placement and applicability rules: research R8. A pack has zero or one inconsistency. The number
of affected packs is `rate × count` rounded half up.

## ApplicantPack (`synthetic/pack.py`)

| Field | Notes |
|---|---|
| `pack_id` | `pack-0001` … `pack-5000`, unique within a run |
| `profile` | the true HouseholdProfile |
| `form` | the form values as the applicant states them, including any altered field; holds the full FR-002 fields plus the `submission` block (exactly the 001 `POST /api/v1/applications` payload) |
| `documents` | the content rendered for each document type, i.e. the values each document shows, including any altered field |
| `inconsistency` | an `Inconsistency` or none |
| `label` | the `LabelResult` from the true profile's facts |
| `expected_routing` | `NEEDS_HUMAN_REVIEW` if `inconsistency` is set, otherwise `label.outcome` (FR-011) |

The answer key (FR-005) is this object serialised; its format is in
[contracts/pack-format.md](./contracts/pack-format.md#answer_keyjson).

## GenerationRequest and GenerationRun (`synthetic/run.py`)

**GenerationRequest** (validated before anything is written):

| Field | Constraint |
|---|---|
| `count` | 1–5000 |
| `seed` | integer ≥ 0 (error: `seed must be zero or a positive integer`) |
| `inconsistency_rate_pct` | 0–100, default 0 |
| `inconsistency_types` | a non-empty subset of the five types, default all |
| `outcome_mix_pct` | none (natural distribution) or `{APPROVE, SOFT_DECLINE, NEEDS_HUMAN_REVIEW}` → integers that sum to 100 |
| `as_of` | date, default `2026-10-01` |
| `output_root` | default `data/synthetic` |
| `overwrite` | bool, default false |

**GenerationRun** is written as `run.json`: `run_id`, the request, `generator_version`,
`policy_version_id`, `generated_at` (UTC, ends in `Z`), `counts` (packs, per eligibility outcome,
per expected routing, per inconsistency type).

## SeedingResult (`synthetic/seeding.py`)

One row per attempted pack in `seeding_report.csv`: `pack_id`, `status` (`submitted` or
`rejected`), `reference_number` (empty if rejected), `returned_outcome`, `eligibility_outcome`,
`matched` (true or false; empty if rejected). Packs not attempted because the application became
unreachable are not listed (FR-020).

## Relationships

```text
GenerationRun 1 ──< ApplicantPack 1 ── 1 HouseholdProfile ──(to_facts)──> HouseholdFacts ──(policy)──> LabelResult
                          │
                          ├── 5 Documents (rendered from profile + form, altered by the Inconsistency)
                          ├── 0..1 Inconsistency
                          └── 0..1 SeedingResult (after `seed`)
```
