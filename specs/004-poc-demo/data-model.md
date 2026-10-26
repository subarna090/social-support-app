# Data Model: PoC Demo (004)

Domain types are frozen dataclasses in `domain/`. Money is `Decimal`, and dates are `date`.

## Domain

### DocumentType (StrEnum)
`BANK_STATEMENT`, `EMIRATES_ID_CARD`, `RESUME`, `ASSETS_LIABILITIES`, `CREDIT_REPORT`. Each has a
display label and an upload field name (`bank_statement`, `emirates_id_card`, `resume`,
`assets_liabilities`, `credit_report`).

### ExtractedDocument
| Field | Type | Notes |
|---|---|---|
| document_type | DocumentType | |
| ok | bool | False if the file is unreadable, of the wrong type, or a required field is missing |
| fields | dict[str, str] | canonical strings: money `1234.00`, dates ISO, lists joined in `items` |
| items | dict[str, tuple[str, ...]] | list-valued fields (resume `skills`, `jobs`) |
| confidence | dict[str, float] | OCR score per field (ID card only; empty for parsed documents) |
| error | str \| None | human-readable reason when not ok, without file content; includes "read with low confidence" when a required ID card field is below `OCR_MIN_CONFIDENCE` |
| duration_ms | int | time taken to read this document |

Fields per type (required ones in **bold**):
- BANK_STATEMENT: **account_holder**, **monthly_income_aed** (average of "Total credits"),
  closing_balance_aed (last month), statement_months.
- EMIRATES_ID_CARD: **full_name**, **emirates_id**, **date_of_birth**.
- RESUME: **months_employed_last_24**, years_experience, last_job_title, education; items:
  skills, jobs.
- ASSETS_LIABILITIES: **total_assets_aed**, **total_liabilities_aed**, net_wealth_aed.
- CREDIT_REPORT: **credit_score**, **active_credit_defaults**, **report_date**, full_name, address.

### CrossCheckResult
| Field | Type |
|---|---|
| check_id | `name_vs_id_card`, `emirates_id_vs_id_card`, `name_vs_bank_holder`, `income_vs_bank` |
| passed | bool \| None (None = skipped because a document failed) |
| form_value / document_value | str |
| sources | tuple[DocumentType, ...] |
| message | str |

Names are compared case-insensitively, with whitespace collapsed. Emirates IDs are compared as
digits only. Income passes when `|declared − bank| ≤ tolerance% × bank`.

### Finding
| Field | Type | Notes |
|---|---|---|
| rule_id | str | TOML rule id, `crosscheck:<check_id>` or `document:<type>` |
| outcome | Outcome | the severity this finding implies |
| text | str | formatted reason |
| sources | tuple[str, ...] | document labels the values came from |

### Assessor input (identity-free)
`DocumentRuleAssessor.assess_case(facts: HouseholdFacts | None, findings: tuple[Finding, ...])`.
The service builds `facts` from the form (family size, employment status) and the extracted values,
and builds `findings` for failed cross-checks (`crosscheck:<id>`) and unreadable documents
(`document:<type>`). `facts` is None when a document it needs failed. The assessor never receives
`ExtractedDocument` or `CrossCheckResult`.

### CaseAssessment
An `AssessmentResult` plus `findings: tuple[Finding, ...]` (the pre-built findings plus the rule
findings). `outcome` is the most severe finding.
`explanation` joins the finding texts. `flag_reason` holds the review findings, joined and
truncated to 200 characters. `suggested_next_steps` is required for SOFT_DECLINE (as before).

### EnablementProfile (sent to the LLM; no identity)
skills, education, years_experience, last_job_title, employment_status, months_employed_last_24,
family_size, outcome, income_band (`below_band` | `borderline` | `above_band` | `unknown`).

### EnablementPlan
training: tuple[str,...], job_matches: tuple[str,...], career_counselling: str, is_fallback: bool,
model: str (`fallback` when is_fallback is true).

### EnablementAdvisor (Protocol)
`advise(profile: EnablementProfile) -> EnablementPlan`. It raises on failure, and the service
substitutes `FALLBACK_PLAN`.

## Rules file `labelling/policies/decision_v1.toml`

The format is the same as 002, and `evaluate_all` treats each rule independently. The last rule is
the required default and is never reported. For the rules, see research R5. Every reason template
states both the value and its threshold, for example "Income per member of {income_per_member_aed}
AED is below the 2000.00 AED band."

## Persistence (new tables, append-only)

| Table | Columns |
|---|---|
| `application_documents` | id, application_id FK, document_type, original_filename, stored_path, sha256, size_bytes, ok, error, fields JSON, items JSON, confidence JSON, duration_ms |
| `cross_check_results` | id, application_id FK, check_id, passed (nullable), form_value, document_value, message |
| `decision_inputs` | id, decision_id FK unique, facts JSON (the `HouseholdFacts` used, or null when skipped), fact_sources JSON (factor → document label) |
| `decision_findings` | id, decision_id FK, sequence, rule_id, outcome, text, sources JSON |
| `enablement_plans` | id, application_id FK, created_at, model, is_fallback, profile JSON (exactly what was sent), latency_ms, error_type (nullable), training JSON, job_matches JSON, career_counselling |

Existing tables are unchanged, so an existing `data/app.db` keeps working because `create_all` adds
only the new tables. Uploaded files are written to `UPLOAD_DIR/<reference>/<document_type><ext>`
after the database commit succeeds. If a write fails, a FAILED `STORED` trace step with the
`error_type` is added; the decision stands.

## Trace steps

The trace for a document submission is: `RECEIVED → VALIDATED → EXTRACTED → CROSS_CHECKED → ASSESSED
→ STORED → RESULT_RETURNED`. The enablement call adds `ENABLEMENT` (`detail` = `<model> <latency_ms>ms`
or `fallback <error_type>`). The EXTRACTED detail lists each document's type, ok flag and duration,
for example `BANK_STATEMENT ok 140ms; EMIRATES_ID_CARD ok 2900ms`. `detail` never holds identity or
amounts.
