# API Contract: Document Extraction (v1 additions)

Base path: `/api/v1`. This extends [001's contract](../../001-application-walking-skeleton/contracts/api.md).
Its conventions hold:

- Money is a 2-dp string, and timestamps are UTC ISO ending in `Z`.
- Validation errors use the flat `{"errors": [{field, message}]}` shape.
- Other errors use `{"detail": "..."}`.

Contract tests check responses against this document.

Draft endpoints are authorised by the unguessable draft id alone (FR-015). An unknown or expired
draft id always gives the same response:

```json
404 {"detail": "This draft was not found or has expired. Start a new application."}
```

Shared types:

- `document_type`: `BANK_STATEMENT` | `EMIRATES_ID` | `RESUME` | `ASSETS_LIABILITIES` |
  `CREDIT_REPORT`
- `status`: `WAITING` | `READING` | `READ` | `FAILED`

---

## POST `/drafts`: start a draft (US2)

**201 Created**
```json
{"draft_id": "Qm3x…43 chars…", "expires_at": "2026-10-26T09:00:00Z", "documents": []}
```

## PUT `/drafts/{draft_id}/documents/{document_type}`: attach or replace (FR-007, FR-008)

`multipart/form-data` with one part named `file`. Attaching a type that is already attached
replaces the earlier document and its extraction.

**202 Accepted**: a [`DocumentOut`](#documentout). Its status is `WAITING`, or `FAILED` straight
away if the type or size check failed (R12).
```json
{
  "document_type": "EMIRATES_ID",
  "filename": "emirates_id.png",
  "size_bytes": 44905,
  "status": "FAILED",
  "failure_reason": "This file is a spreadsheet, but an ID card image was expected.",
  "attached_at": "2026-10-25T09:00:04Z",
  "extraction": null
}
```

**422**: unknown `document_type`, or no `file` part:
`{"errors": [{"field": "document_type", "message": "…"}]}`.

Oversized files are **not** rejected with 413. They are recorded as `FAILED` ("This file is larger
than 10 MB.") and count as attached (spec edge cases, FR-018).

## DELETE `/drafts/{draft_id}/documents/{document_type}`: remove before submitting (FR-007)

**204 No Content**. Removing a type that isn't attached also gives 204.

## GET `/drafts/{draft_id}`: progress and extracted values (FR-008, FR-009)

**200 OK**
```json
{
  "draft_id": "Qm3x…",
  "expires_at": "2026-10-26T09:00:00Z",
  "missing_types": ["CREDIT_REPORT"],
  "ready_to_submit": false,
  "documents": [ {"document_type": "BANK_STATEMENT", "status": "READ", "...": "DocumentOut"} ]
}
```
`ready_to_submit` is true when all five types are attached and none is `WAITING` or `READING`.

### DocumentOut

```json
{
  "document_type": "BANK_STATEMENT",
  "filename": "bank_statement.pdf",
  "size_bytes": 4966,
  "status": "READ",
  "failure_reason": null,
  "attached_at": "2026-10-25T09:00:03Z",
  "extraction": {
    "method": "bank-statement-parser/1",
    "method_versions": {"pypdf": "6.21.2"},
    "finished_at": "2026-10-25T09:00:04Z",
    "warnings": [],
    "fields": [
      {"path": "bank_statement.account_holder", "label": "Account holder", "value": "Rashid Farouk",
       "confidence": "1.00", "uncertain": false, "routing": false},
      {"path": "bank_statement.income_credits[0].amount_aed", "label": "Income credit 1: amount (AED)",
       "value": "12350.00", "confidence": "1.00", "uncertain": false, "routing": false},
      {"path": "bank_statement.months[4].total_income_credits_aed", "label": "Sep 2026: total income credits (AED)",
       "value": "12350.00", "confidence": "1.00", "uncertain": false, "routing": true},
      {"path": "bank_statement.address", "label": "Address", "value": null,
       "confidence": null, "uncertain": false, "routing": false}
    ]
  }
}
```
`value: null` means **not found**. The response has no fields for editing values: extracted values
are read-only (FR-009, FR-011). `extraction` is `null` while the document is `WAITING` or
`READING`, and for documents that failed their upload checks.

## POST `/drafts/{draft_id}/comparison`: form vs documents (FR-010)

**Request**: the form's current covered values. Every field is optional; an empty or invalid value
is treated as missing.
```json
{"full_name": "Rashid Farouk", "emirates_id": "784-1973-0000001-1", "family_size": 8,
 "net_monthly_income_aed": "11000.00", "employment_status": "EMPLOYED"}
```

**200 OK**
```json
{
  "fields": [
    {"field": "net_monthly_income_aed", "form_value": "11000.00", "document_value": "12350.00",
     "document_label": "Bank statement, total income credits for Sep 2026",
     "source": "BANK_STATEMENT", "available": true, "differs": true, "document_value_uncertain": false},
    {"field": "employment_status", "form_value": "EMPLOYED", "document_value": "Currently working",
     "document_label": "Resume, current job", "source": "RESUME",
     "available": true, "differs": false, "document_value_uncertain": false},
    {"field": "family_size", "form_value": "8", "document_value": null,
     "document_label": "Credit report, household members on file plus the applicant", "source": "CREDIT_REPORT",
     "available": false, "differs": false, "document_value_uncertain": false}
  ]
}
```
There is always one entry for each of the 5 covered fields. Comparison ignores formatting (research
R10). Nothing is stored.

---

## POST `/applications`: submit (changed: FR-012, FR-013, FR-019)

**Request**: 001's body **plus** a required `draft_id`:
```json
{"draft_id": "Qm3x…", "full_name": "Rashid Farouk", "emirates_id": "784-1973-0000001-1",
 "family_size": 8, "net_monthly_income_aed": "12350.00", "employment_status": "EMPLOYED"}
```

**201 Created**: 001's shape, plus `documents`, a summary of each stored document's status:
```json
{
  "reference_number": "SSA-7K2M9QXH4D",
  "submitted_at": "…Z",
  "previous_application_exists": false,
  "decision": {
    "outcome": "NEEDS_HUMAN_REVIEW",
    "income_per_member_aed": null,
    "explanation": "Some documents could not be read reliably, so a caseworker will review this application. The resume could not be read: the language model is unavailable. Rule: extraction-gate/v1.",
    "suggested_next_steps": [],
    "flag_reason": "extraction: resume failed",
    "rule_version": "extraction-gate/v1",
    "decided_at": "…Z"
  },
  "documents": [{"document_type": "RESUME", "status": "FAILED"}, "…"]
}
```
When the gate is clear, `decision` is exactly what the configured assessor returns, as in 001.

**422**: field errors as in 001, plus:
- `{"field": "draft_id", "message": "Attach your documents before submitting."}` when `draft_id` is
  absent. **Every** submission path needs documents (FR-013).
- `{"field": "documents", "message": "Attach the missing documents: Resume, Credit report."}`.
  Nothing is stored.
- `{"field": "documents", "message": "Wait until all documents have been read."}` while any
  document is `WAITING` or `READING`. Nothing is stored.

**404**: an unknown or expired `draft_id` (the draft 404 body above).

On success the draft is consumed. Re-submitting the same `draft_id` gives 404.

---

## GET `/caseworker/applications/{reference_number}`: caseworker view (FR-020)

Header `X-Caseworker-Passcode`. A missing or wrong passcode gives **401**
`{"detail": "Access denied."}`, as for the review queue.

This works for any submitted application, whatever its outcome (Clarification, 2026-10-25).

**200 OK**
```json
{
  "reference_number": "SSA-7K2M9QXH4D",
  "submitted_at": "…Z",
  "application": {"full_name": "…", "emirates_id": "…", "family_size": 8,
                  "net_monthly_income_aed": "11000.00", "employment_status": "EMPLOYED"},
  "decision": { "...": "DecisionOut as in 001" },
  "comparison": [ "FieldComparison entries, as returned by /comparison, for the submitted form values" ],
  "documents": [
    {"document_type": "EMIRATES_ID", "filename": "emirates_id.png", "media_type": "image/png",
     "size_bytes": 44905, "status": "READ", "failure_reason": null, "available": true,
     "extraction": { "...": "as in DocumentOut, plus confidence_threshold" }}
  ],
  "problems": ["The name on the ID card was read with low confidence (0.96)."]
}
```
`available` is false when the original was not stored (oversized). Applications submitted before
this feature have `documents: []`.

**404** `{"detail": "No application found."}` for an unknown reference.

## GET `/caseworker/applications/{reference_number}/documents/{document_type}`: original file (FR-016, FR-020)

The same passcode header is required. **200** returns the original bytes unchanged, with the stored
`media_type` and `Content-Disposition: inline; filename="…"`. **404** when the application, the
document or its content does not exist.

---

## GET `/health` (changed)

Adds an `extraction` object, so the UI and the quickstart can tell when the models are ready:
```json
{"status": "ok", "assessor": "income_rule", "rule_version": "…",
 "extraction": {"ocr": "ready", "llm": "ready", "llm_model": "qwen2.5:7b", "queue_length": 0}}
```
`ocr` is one of `loading`, `ready` or `unavailable`. `llm` is `ready` or `unavailable`, based on
whether Ollama is reachable and the model is present. `status` stays `ok` even when extraction is
unavailable, because the app still works and affected documents fail and go to review.
