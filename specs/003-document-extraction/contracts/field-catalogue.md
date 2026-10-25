# Field Catalogue

The fields each extractor produces (FR-002), the answer-key value each is scored against (FR-023),
and which ones are **routing fields** (FR-019) or feed a **covered form field** (FR-010). It is
implemented as one table in `extraction/catalogue.py` (research R7); a unit test asserts that code
and this document agree.

Paths are `<document>.<field>`. Indexed paths (`[i]`) are lists in document order. Answer-key paths
are relative to `answer_key.json → documents.<document>` (feature 002, `pack-format/1`).

Legend: **R** = routing field (uncertain ⇒ Needs Human Review). **C** = feeds a covered form field.

## Bank statement (`bank_statement`, parser, research R3)

| Path | Kind | Answer key | R | C |
|---|---|---|---|---|
| `account_holder` | text | `account_holder` | | |
| `address` | text | `address` | | |
| `period_start` | month | `period_start` | | |
| `period_end` | month | `period_end` | | |
| `months[i].month` | month | `months[i].month` | | |
| `months[i].income_credits[j].description` | text | credit transactions of `months[i].transactions` | | |
| `months[i].income_credits[j].amount_aed` | money | (same) `.credit_aed` | | |
| `months[i].total_income_credits_aed` | money | `monthly_income_credits_aed` | | |
| `months[i].closing_balance_aed` | money | `months[i].closing_balance_aed` | | |
| `monthly_income_credits_aed` | money | `monthly_income_credits_aed` (the most recent month's total) | R | C: net monthly household income |

## Emirates ID card (`emirates_id`, OCR, research R6)

| Path | Kind | Answer key | R | C |
|---|---|---|---|---|
| `full_name` | text | `full_name` | R | C: full name |
| `emirates_id` | emirates_id | `emirates_id` | R | C: Emirates ID |
| `nationality` | text | `nationality` | | |
| `date_of_birth` | date | `date_of_birth` | R | |
| `sex` | enum (M, F) | `sex` | | |
| `expiry_date` | date | `expiry_date` | | |

Nationality and sex are extracted because FR-002 lists them, and they are stored with the
document. They are **never** used for routing, comparison or assessment (Constitution IV).

## Resume (`resume`, contacts by parser and history by LLM, research R5)

| Path | Kind | Answer key | R | C |
|---|---|---|---|---|
| `full_name` | text | `full_name` | | |
| `email` | text | `email` | | |
| `phone` | text | `phone` | | |
| `address` | text | `address` | | |
| `jobs[i].employer` | text | `jobs[i].employer` | | |
| `jobs[i].title` | text | `jobs[i].title` | | |
| `jobs[i].start` | month | `jobs[i].start` | | |
| `jobs[i].end` | month or `Present` | `jobs[i].end` (null ⇔ `Present`) | | |
| `current_employer` | text | `current_employer` (null ⇔ not found, reported as "none") | | |
| `education.institution` | text | `university` | | |
| `education.graduation_year` | integer | `graduation_year` | | |
| `employment_status` | enum (`WORKING`, `NOT_WORKING`) | derived from `current_employer` | R | C: employment status |

`employment_status` is derived, not scored on its own. Its accuracy follows from
`current_employer`.

## Assets and liabilities (`assets_liabilities`, spreadsheet, research R4)

| Path | Kind | Answer key | R | C |
|---|---|---|---|---|
| `assets[i].kind` | text | `assets[i].kind` | | |
| `assets[i].description` | text | `assets[i].description` | | |
| `assets[i].value_aed` | money | `assets[i].value_aed` | | |
| `liabilities[i].kind` | text | `liabilities[i].kind` | | |
| `liabilities[i].lender` | text | `liabilities[i].lender` | | |
| `liabilities[i].outstanding_aed` | money | `liabilities[i].outstanding_aed` | | |
| `liabilities[i].monthly_payment_aed` | money | `liabilities[i].monthly_payment_aed` | | |
| `total_assets_aed` | money | `total_assets_aed` | | |
| `total_liabilities_aed` | money | `total_liabilities_aed` | | |
| `net_wealth_aed` | money | `net_wealth_aed` | | |

Kinds are compared after normalisation: the sheet shows `Credit Card`, the key has `CREDIT_CARD`,
and the text rule folds `_` to a space.

## Credit report (`credit_report`, parser, research R3)

| Path | Kind | Answer key | R | C |
|---|---|---|---|---|
| `full_name` | text | `full_name` | | |
| `emirates_id` | emirates_id | `emirates_id` | | |
| `date_of_birth` | date | `date_of_birth` | | |
| `address` | text | `address` | | |
| `household_members[i].name` | text | `household_members[i].name` | | |
| `household_members[i].relationship` | enum | `household_members[i].relationship` | | |
| `household_members[i].age` | integer | `household_members[i].age` | | |
| `household_size` | integer | `len(household_members) + 1` (derived) | R | C: family size |
| `credit_score` | integer | `credit_score` | | |
| `active_credit_defaults` | integer | `active_credit_defaults` | | |
| `accounts[i].lender` | text | `accounts[i].lender` | | |
| `accounts[i].kind` | text | `accounts[i].kind` | | |
| `accounts[i].balance_aed` | money | `accounts[i].balance_aed` | | |
| `accounts[i].status` | text | `accounts[i].status` | | |

## Routing fields, in summary (FR-019)

- `emirates_id.full_name`
- `emirates_id.emirates_id`
- `emirates_id.date_of_birth`
- `bank_statement.monthly_income_credits_aed`
- `credit_report.household_size`
- `resume.employment_status`

These are the values compared with the form, plus the ID card's identity fields (Clarification,
2026-10-25). The routing gate also triggers on any `FAILED` document, regardless of fields.

## Injected inconsistencies (feature 002) and what this feature does with them

Each document is scored against what it shows (FR-023), so an injected inconsistency that is
extracted correctly counts as a match. In the form view (FR-010):

| 002 type | What is altered | What the applicant sees before submitting |
|---|---|---|
| `INCOME_MISMATCH` | the form's income | income highlighted (form vs bank statement) |
| `IDENTITY_MISMATCH` | the ID card's name or number | name or Emirates ID highlighted (form vs card) |
| `FAMILY_SIZE_MISMATCH` | the form's family size | family size highlighted (form vs credit report + 1) |
| `ADDRESS_MISMATCH` | the credit report's address | nothing: address is not a covered field; judged by 004 |
| `EMPLOYMENT_MISMATCH` | the resume's employer | usually nothing: the working status still agrees; judged by 004 |

Highlights never route the case to review in this feature. Judging discrepancies is feature 004
(spec Assumptions).
