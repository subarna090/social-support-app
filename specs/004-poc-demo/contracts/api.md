# API Contract additions (004)

All paths are under `/api/v1`. Existing 001 endpoints are unchanged except where noted below.

## POST /applications/with-documents

`multipart/form-data`.

| Part | Kind | Rules |
|---|---|---|
| full_name, emirates_id, family_size, net_monthly_income_aed, employment_status | text | same validation as the 001 JSON submit |
| bank_statement | file | required |
| emirates_id_card | file | required |
| resume | file | required |
| assets_liabilities | file | required |
| credit_report | file | required |

**422**: invalid form fields or missing files, as `{"errors": [{"field": "resume", "message": "Attach
the resume."}]}`.

**201** (a bad or unreadable file does **not** give an error status: it becomes a review finding):

```json
{
  "reference_number": "SSA-…",
  "submitted_at": "…Z",
  "previous_application_exists": false,
  "decision": {
    "outcome": "NEEDS_HUMAN_REVIEW",
    "income_per_member_aed": "2250.00",
    "explanation": "…",
    "suggested_next_steps": [],
    "flag_reason": "…",
    "rule_version": "decision/v1+ab12cd34",
    "decided_at": "…Z",
    "findings": [
      {"rule_id": "crosscheck:income_vs_bank", "outcome": "NEEDS_HUMAN_REVIEW",
       "text": "Declared income 7000.00 AED differs from bank statement income 9000.00 AED by more than 10%.",
       "sources": ["Application form", "Bank statement"]}
    ]
  },
  "documents": [
    {"document_type": "BANK_STATEMENT", "label": "Bank statement", "ok": true, "error": null,
     "fields": {"account_holder": "…", "monthly_income_aed": "9000.00"}, "items": {}}
  ],
  "cross_checks": [
    {"check_id": "income_vs_bank", "passed": false, "form_value": "7000.00",
     "document_value": "9000.00", "message": "…"}
  ]
}
```

`decision.findings` is also added (possibly empty) to the 001 submit and lookup responses.
`documents` and `cross_checks` appear only here.

## POST /applications/{reference_number}/enablement

Body `{"emirates_id": "784-…"}`. The 404 response is identical to the lookup 404 for both an unknown
reference and a mismatched ID. It returns the stored plan if one exists; otherwise it generates one
(taking up to `ENABLEMENT_TIMEOUT_S`) and stores it.

**200**:
```json
{"training": ["…"], "job_matches": ["…"], "career_counselling": "…",
 "is_fallback": false, "model": "qwen2.5:7b", "created_at": "…Z"}
```

The plan never changes the decision.

## GET /review-queue (changed)

Each item gains `"reasons": ["…", "…"]`, the text of the NEEDS_HUMAN_REVIEW findings (empty for
001-style decisions). `flag_reason` is kept.

## GET /health (changed)

Adds `"enablement_model"`.
