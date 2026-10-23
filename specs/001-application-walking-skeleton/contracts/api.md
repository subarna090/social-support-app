# API Contract: Application Walking Skeleton (v1)

Base path: `/api/v1`. All bodies are JSON. Money values are **strings** with 2 decimal places, so
Decimal precision survives JSON. Timestamps are ISO 8601 UTC. FastAPI also publishes the live
OpenAPI schema at `/docs` and `/openapi.json`. Contract tests check against this document.

---

## POST `/api/v1/applications`: submit an application (US1, FR-001–FR-010, FR-015–FR-017)

**Request**
```json
{
  "full_name": "Aisha Al Mansoori",
  "emirates_id": "784-1990-1234567-1",
  "family_size": 4,
  "net_monthly_income_aed": "6000.00",
  "employment_status": "EMPLOYED"
}
```

**201 Created**
```json
{
  "reference_number": "SSA-7K2M9QXH4D",
  "submitted_at": "2026-10-23T10:15:02Z",
  "previous_application_exists": false,
  "decision": {
    "outcome": "APPROVE",
    "income_per_member_aed": "1500.00",
    "explanation": "Net monthly household income of 6000.00 AED across 4 members gives 1500.00 AED per member, which is below the 2000.00 AED support threshold. Employment status: Employed. Rule: income-per-member/v0.1+3fa2c1d9.",
    "suggested_next_steps": [],
    "flag_reason": null,
    "rule_version": "income-per-member/v0.1+3fa2c1d9",
    "decided_at": "2026-10-23T10:15:02Z"
  }
}
```

**422 Unprocessable Entity**: validation failed (FR-002, FR-003). Nothing is stored.
```json
{
  "errors": [
    {"field": "emirates_id", "message": "Emirates ID must be 15 digits in the format 784-YYYY-NNNNNNN-N."},
    {"field": "family_size", "message": "Family size must be a whole number from 1 to 20."}
  ]
}
```
FastAPI's default 422 body is replaced with this flat `errors[]` shape, which gives one entry per
field, so the UI can show messages next to each field.

**Notes**: the response never contains the internal `id`. If assessment fails, the response is
still `201`, with `outcome = NEEDS_HUMAN_REVIEW` and `flag_reason = "automatic assessment
unavailable"` (FR-015).

---

## POST `/api/v1/applications/lookup`: retrieve a decision (US2, FR-011)

**Request**
```json
{"reference_number": "SSA-7K2M9QXH4D", "emirates_id": "784199012345671"}
```
The Emirates ID may be sent with or without dashes and is normalised before comparison.

**200 OK**: the same shape as the `201` above, plus the submitted details:
```json
{
  "reference_number": "SSA-7K2M9QXH4D",
  "submitted_at": "2026-10-23T10:15:02Z",
  "previous_application_exists": false,
  "application": {
    "full_name": "Aisha Al Mansoori",
    "emirates_id": "784-1990-1234567-1",
    "family_size": 4,
    "net_monthly_income_aed": "6000.00",
    "employment_status": "EMPLOYED"
  },
  "decision": { "...": "identical to the decision returned at submission" }
}
```

**404 Not Found**: the reference doesn't exist **or** the Emirates ID doesn't match. The body is
byte-for-byte identical in both cases:
```json
{"detail": "No application found for the details provided."}
```

---

## GET `/api/v1/review-queue`: caseworker review list (US3, FR-012)

**Headers**: `X-Caseworker-Passcode: <passcode>` (required)

**200 OK**: applications with outcome `NEEDS_HUMAN_REVIEW`, newest first:
```json
{
  "items": [
    {
      "reference_number": "SSA-Q4M8ZK2R1C",
      "full_name": "Omar Haddad",
      "submitted_at": "2026-10-23T10:20:44Z",
      "flag_reason": "borderline income"
    }
  ]
}
```
When there are no items, the response is `{"items": []}` and the UI shows its empty state.

**401 Unauthorized**: the header is missing, wrong, or no passcode is configured on the server.
No data is returned.
```json
{"detail": "Access denied."}
```

---

## GET `/api/v1/health`: liveness check

**200 OK**: `{"status": "ok", "assessor": "income_rule", "rule_version": "income-per-member/v0.1+3fa2c1d9"}`

---

## Guarantees across all endpoints

- There are **no** PUT, PATCH or DELETE routes for applications or decisions (FR-009, R8).
- Responses and logs never contain the internal database ids. Logs never contain the Emirates ID
  or income values (Principle I).
- The Streamlit UI uses only these endpoints (R1).
