# Output Contract: Run Folder and Pack Format

Format version: `pack-format/1`. Later features (003 extraction, 004 validation, 005 ML) read
these files. Any breaking change bumps the version recorded in `run.json`.

## Layout

```text
data/synthetic/<run-id>/              # run id: s<seed>-n<count>-<settings hash[:6]>
├── run.json                          # GenerationRun
├── summary.csv                       # one row per pack
├── seeding_report.csv                # only after `seed`
└── packs/
    └── pack-0001/
        ├── form.json                 # what the applicant states (may contain the altered value)
        ├── answer_key.json           # ground truth
        ├── bank_statement.pdf
        ├── emirates_id.png
        ├── resume.pdf
        ├── assets_liabilities.xlsx
        └── credit_report.pdf
```

Every PDF page, the PNG, and every sheet of the xlsx (in cell A1) carries
`SYNTHETIC – NOT A REAL DOCUMENT`.

## `form.json`

```json
{
  "pack_id": "pack-0001",
  "full_name": "Aisha Al Mansoori",
  "emirates_id": "784-1990-0000001-0",
  "date_of_birth": "1990-04-12",
  "address": {"unit": "Villa 12", "street": "Street 7", "district": "Al Waha District", "emirate": "Sharjah"},
  "email": "aisha.almansoori@example.com",
  "phone": "+971 50 000 1234",
  "family_size": 4,
  "family_members": [{"name": "Omar Al Mansoori", "relationship": "SPOUSE", "age": 38}],
  "net_monthly_income_aed": "6000.00",
  "employment_status": "EMPLOYED",
  "employer": "Oasis Logistics (Demo) LLC",
  "submission": {
    "full_name": "Aisha Al Mansoori",
    "emirates_id": "784-1990-0000001-0",
    "family_size": 4,
    "net_monthly_income_aed": "6000.00",
    "employment_status": "EMPLOYED"
  }
}
```

`submission` is exactly the body of the 001 `POST /api/v1/applications` request.

## `answer_key.json`

```json
{
  "format": "pack-format/1",
  "run_id": "s42-n100-3fa2c1",
  "pack_id": "pack-0001",
  "profile": { "...": "the full HouseholdProfile (data-model.md), including nationality and gender" },
  "facts": { "family_size": 4, "net_monthly_income_aed": "6000.00", "income_per_member_aed": "1500.00",
             "employment_status": "EMPLOYED", "months_employed_last_24": 24,
             "total_assets_aed": "45000.00", "total_liabilities_aed": "12000.00", "net_wealth_aed": "33000.00",
             "credit_score": 712, "active_credit_defaults": 0 },
  "documents": {
    "form":                  {"full_name": "...", "emirates_id": "...", "net_monthly_income_aed": "6000.00", "...": "..."},
    "bank_statement":        {"account_holder": "...", "monthly_salary_credit_aed": "6000.00", "statement_months": 3, "...": "..."},
    "emirates_id":           {"full_name": "...", "emirates_id": "...", "date_of_birth": "...", "nationality": "...", "...": "..."},
    "resume":                {"full_name": "...", "current_employer": "...", "jobs": [], "...": "..."},
    "assets_liabilities":    {"total_assets_aed": "45000.00", "total_liabilities_aed": "12000.00", "net_wealth_aed": "33000.00", "...": "..."},
    "credit_report":         {"full_name": "...", "emirates_id": "...", "address": "...", "household_members": [], "credit_score": 712, "active_credit_defaults": 0, "...": "..."}
  },
  "inconsistency": null,
  "eligibility": {
    "outcome": "APPROVE",
    "rule_id": "low_income_stable_work",
    "compared": {"months_employed_last_24": 24},
    "reason": "Income per member is below 2000.00 AED and the applicant worked 24 of the last 24 months.",
    "policy_version_id": "eligibility/v1+8c1d2e4f"
  },
  "expected_routing": "APPROVE"
}
```

- `documents.<type>` holds the value of every field **as shown in that document** (values only, no
  positions; clarify Q3), in canonical form: money as `"6000.00"`, dates as `YYYY-MM-DD`. Documents
  display money with thousands separators (`6,000.00 AED`), so consumers compare after formatting. With no inconsistency, every shared field agrees with `profile`.
- `documents.bank_statement` also holds `months`: for each statement month, every transaction
  (`date`, `description`, `credit_aed`, `debit_aed`, `balance_aed`) and the `closing_balance_aed`,
  plus `rent` (description and amount, or null for households with a mortgage). The PDF draws
  exactly these rows.
- `inconsistency`, when present:
  `{"type": "INCOME_MISMATCH", "documents": ["form", "bank_statement"], "field": "net_monthly_income_aed", "true_value": "6000.00", "altered_value": "4200.00"}`.
- `expected_routing` is `NEEDS_HUMAN_REVIEW` when `inconsistency` is present, otherwise
  `eligibility.outcome`.

## `summary.csv`

UTF-8, comma-separated, header row, one row per pack in pack id order.

| Column | Type | Use |
|---|---|---|
| `pack_id` | str | key |
| `family_size` … `active_credit_defaults` | the 10 `HouseholdFacts` fields, in data-model order | model features (true values) |
| `eligibility_outcome` | APPROVE, SOFT_DECLINE or NEEDS_HUMAN_REVIEW | **label** for feature 005 |
| `eligibility_rule_id` | str | explanation and analysis |
| `expected_routing` | same values as `eligibility_outcome` | label for feature 004 validation |
| `inconsistency_count` | 0 or 1 | analysis |
| `inconsistency_types` | str, `;`-separated, empty if none | analysis |
| `audit_nationality`, `audit_gender` | str | **not model inputs**: for fairness evaluation only (Constitution IV) |

## `run.json`

```json
{
  "format": "pack-format/1",
  "run_id": "s42-n100-3fa2c1",
  "request": {"count": 100, "seed": 42, "inconsistency_rate_pct": 30, "inconsistency_types": ["INCOME_MISMATCH", "ADDRESS_MISMATCH"],
              "outcome_mix_pct": {"APPROVE": 40, "SOFT_DECLINE": 40, "NEEDS_HUMAN_REVIEW": 20}, "as_of": "2026-10-01"},
  "generator_version": "0.1.0",
  "policy_version_id": "eligibility/v1+8c1d2e4f",
  "generated_at": "2026-10-24T09:30:00Z",
  "counts": {"packs": 100,
             "eligibility": {"APPROVE": 40, "SOFT_DECLINE": 40, "NEEDS_HUMAN_REVIEW": 20},
             "expected_routing": {"APPROVE": 28, "SOFT_DECLINE": 29, "NEEDS_HUMAN_REVIEW": 43},
             "inconsistencies": {"INCOME_MISMATCH": 12, "ADDRESS_MISMATCH": 18}}
}
```

## `seeding_report.csv`

Columns: `pack_id, status, reference_number, returned_outcome, eligibility_outcome, matched`
(data-model.md, SeedingResult).
