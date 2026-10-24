# Contract: Labelling Policy File

Policies live in `src/social_support/labelling/policies/` as TOML files, one per version, and are
loaded with `load_policy(name="eligibility", version="v1")`. Feature 005 reuses the same loader and
evaluator. The version id is `<name>/<version>+<hash>`, where `<hash>` is the first 8 hex chars of
the SHA-256 of the file text with line endings normalised to `\n`. Any edit to the file, even to a
comment, yields a new id, while a Windows checkout with CRLF line endings yields the same id as
everyone else.

## Format

```toml
name = "eligibility"
version = "v1"
description = "Eligibility labels for synthetic applicant packs (feature 002)."
# Rules are evaluated top to bottom; the first rule whose conditions all hold decides.
# A later rule therefore only sees households that matched none of the earlier rules.

[[rules]]
id = "high_net_wealth"
outcome = "SOFT_DECLINE"
reason = "Net wealth of {net_wealth_aed} AED is above the 500000.00 AED limit."
conditions = [{ factor = "net_wealth_aed", op = "gt", value = 500000 }]

# ... rules 2–7 as in research.md R3 ...

[[rules]]
id = "unstable_work_history"
outcome = "NEEDS_HUMAN_REVIEW"
reason = "Income per member is below 2000.00 AED but the applicant worked only {months_employed_last_24} of the last 24 months."
conditions = []
```

## Rules for a valid file

| Check | Error raised on load |
|---|---|
| `name`, `version` and at least one rule are present | `PolicyError: policy has no rules` |
| Rule ids are unique and snake_case | `PolicyError: duplicate rule id <id>` |
| `outcome` is APPROVE, SOFT_DECLINE or NEEDS_HUMAN_REVIEW | `PolicyError: unknown outcome <x> in rule <id>` |
| `factor` is a `HouseholdFacts` field | `PolicyError: unknown factor <f> in rule <id>` |
| `op` is one of `lt le gt ge eq in`; `in` takes a list | `PolicyError: unknown operator <op> in rule <id>` |
| Only the last rule has empty `conditions` | `PolicyError: the last rule must be the default (no conditions)` |
| `reason` only uses placeholders that are `HouseholdFacts` fields | `PolicyError: unknown placeholder {p} in rule <id>` |

Numeric comparisons convert `value` to `Decimal`, so `2000` and `2000.00` behave the same. Money
values in rendered reasons are formatted with 2 decimal places.

## Evaluation

`policy.evaluate(facts: HouseholdFacts) -> LabelResult`: pure and deterministic, with no I/O after
loading. `LabelResult.compared` holds exactly the factors named in the matching rule's conditions;
for the default rule it holds the factors used in its reason.
