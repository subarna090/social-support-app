# Feature Specification: PoC Demo — Documents to Decision and Enablement

**Feature Branch**: `004-poc-demo`

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Feature 004 PoC demo, condensed for a demo this week. An applicant fills
the interactive application form and manually uploads five documents (bank statement, Emirates ID
image, resume, assets/liabilities spreadsheet, credit report). The system extracts fields with
simple local tools only (no LLM in extraction), runs a few cross-checks between form and documents,
assesses eligibility on income per member, employment history, family size, net wealth and credit
standing, and recommends APPROVE, SOFT_DECLINE or NEEDS_HUMAN_REVIEW with reasons. Economic
enablement recommendations come only from a locally hosted LLM using the anonymised profile, with a
fixed fallback. Three fixed demo packs, one per outcome. Out of scope: agent orchestration, ML
classifier, observability, vector store, strict compliance."

Scope decisions (2026-10-26, from the user): condensed Spec Kit flow; exactly three demo use cases
(auto-approve, soft decline with reasons, human review with reasons); documents are uploaded
manually by the presenter; the resume is read by plain text parsing, no LLM.

This feature is built from `main` (001 + 002). It does not depend on the separate
`003-document-extraction` branch, which stays as a fuller future design.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-approval from uploaded documents (Priority: P1)

An applicant fills in the application form (name, Emirates ID, family size, declared monthly income,
employment status) and uploads their five documents. Within a short wait, the system shows the
outcome **APPROVE**, the reasons for it (for example "income per member of 1,450.00 AED is below the
2,000.00 AED band; net wealth 42,000.00 AED is below the limit; credit score 702 with no defaults;
documents agree with the form"), and the values it read from each document.

**Why this priority**: this is the headline of the demo: a decision in minutes instead of 5–20
working days, straight from the documents.

**Independent Test**: upload the "approve" demo pack with its form values; the result is APPROVE,
every reason cites a value, and each value names the document it came from.

**Acceptance Scenarios**:

1. **Given** the approve demo pack, **When** the presenter submits the form with all five files,
   **Then** the outcome is APPROVE with at least one reason per assessed factor (income per member,
   employment, net wealth, credit) and a reference number is shown.
2. **Given** a submitted application, **When** the result is shown, **Then** the extracted values
   are listed per document (bank statement, ID card, resume, assets/liabilities, credit report).

---

### User Story 2 - Soft decline with reasons (Priority: P1)

An applicant whose household is clearly outside the support criteria (income per member clearly
above the band, or net wealth above the limit) receives **SOFT_DECLINE**, the specific reasons, and
next steps (for example "you may reapply if your household income changes").

**Why this priority**: shows that negative outcomes are explained and never final hard declines.

**Independent Test**: upload the "soft decline" demo pack; the outcome is SOFT_DECLINE, the reasons
name the failing factor(s) with their values, and at least one next step is shown.

**Acceptance Scenarios**:

1. **Given** the soft-decline demo pack, **When** it is submitted, **Then** the outcome is
   SOFT_DECLINE with the failing factor and its value in the reasons and at least one next step.

---

### User Story 3 - Human review with reasons (Priority: P1)

An applicant whose case is uncertain (borderline income, a mismatch between the form and the
documents, credit defaults or a poor score, an unstable work history, or a document that could not
be read) receives **NEEDS_HUMAN_REVIEW** with the reasons. The case appears in the existing
passcode-protected caseworker review queue with those reasons.

**Why this priority**: shows human-in-the-loop for uncertain cases and exercises the cross-checks.

**Independent Test**: upload the "review" demo pack (which contains a deliberate form/document
mismatch); the outcome is NEEDS_HUMAN_REVIEW, the reason names the mismatch and the documents
involved, and the case is listed in the caseworker queue.

**Acceptance Scenarios**:

1. **Given** the review demo pack, **When** it is submitted, **Then** the outcome is
   NEEDS_HUMAN_REVIEW and the reasons name each failed cross-check with both values (form vs
   document).
2. **Given** that submitted case, **When** a caseworker opens the review queue with the passcode,
   **Then** the case is listed with its reasons.
3. **Given** an upload where a document cannot be read, **When** it is submitted, **Then** the
   outcome is NEEDS_HUMAN_REVIEW with a reason naming the unreadable document.

---

### User Story 4 - Economic enablement recommendations (Priority: P2)

After the decision, the applicant sees economic enablement recommendations tailored to their
profile: upskilling or training suggestions, job types that match their skills and experience, and
a career-counselling note. These are written by a locally hosted language model from an anonymised
profile (skills, education, years of experience, last role, employment status, outcome). If the
model is unavailable or slow, a fixed general recommendation is shown and the decision is
unaffected.

**Why this priority**: required by the brief and visible in the demo, but the decision must work
without it.

**Independent Test**: submit any demo pack with the local model running and check the three
recommendation sections refer to the applicant's actual skills or role; stop the model and check
the fallback appears and the decision is unchanged.

**Acceptance Scenarios**:

1. **Given** the local model is running, **When** a decision is shown, **Then** recommendations
   appear in three sections (training, job matching, career counselling), each with at least one item.
2. **Given** the local model is not running, **When** a decision is shown, **Then** a clearly
   labelled general fallback recommendation appears and the outcome and reasons are identical.
3. **Given** any request to the model, **Then** it contains no name, Emirates ID or exact income.

---

### User Story 5 - Reproducible demo packs (Priority: P2)

The presenter can generate the three demo applicant packs (approve, soft decline, review) with one
command. Each pack has the five documents and a small file with the form values to type in. Running
the command again gives the same packs.

**Why this priority**: the demo must be repeatable and must not depend on a random draw.

**Independent Test**: run the command twice; the three packs are identical, and each produces its
intended outcome when submitted.

**Acceptance Scenarios**:

1. **Given** the command is run, **Then** three folders are produced, one per outcome, each with
   five documents and the form values.

### Edge Cases

- A required document is missing: submission is refused with a message naming the missing document.
- A file is empty, corrupt, the wrong type, or over 10 MB: the application is still submitted and
  routed to NEEDS_HUMAN_REVIEW with the document named in the reason.
- The ID card text cannot be read well enough to find the ID number, or is read with low
  confidence: treated as an unreadable document (human review).
- Declared income differs from bank income credits by only a little: within the tolerance it passes.
- Several review reasons and a soft-decline reason apply at once: human review wins, because a
  caseworker must look at uncertain cases before any negative outcome; all reasons are listed.
- The language model returns text that is not in the expected shape: the fallback is shown.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application form MUST collect name, Emirates ID, family size, declared net
  monthly income and employment status (as in feature 001), plus five mandatory file uploads: bank
  statement, Emirates ID card image, resume, assets/liabilities spreadsheet, credit report.
- **FR-002**: Submission MUST be refused, with the missing document named, if any of the five
  uploads is absent.
- **FR-003**: The system MUST extract, using local non-LLM tools only:
  - bank statement: account holder, average monthly income credits (all sources: salary,
    business, rental, pension, benefits), closing balance;
  - ID card: name, ID number, date of birth (by optical character recognition);
  - resume: skills, education, work history (roles and dates), from which months employed in the
    last 24 months and years of experience are derived;
  - assets/liabilities: total assets, total liabilities;
  - credit report: name, credit score, number of active defaults, and address if present.
- **FR-004**: Every extracted value MUST record which document it came from.
- **FR-005**: The system MUST run these cross-checks and record each result: form name vs ID card
  name; form Emirates ID vs ID card number; declared income vs average monthly bank income credits
  (within a configurable tolerance, default 10%); form name vs bank account holder.
- **FR-006**: The system MUST assess eligibility from document-derived values (income from the bank
  statement, wealth from the spreadsheet, credit from the credit report, employment from the resume)
  together with family size from the form, using an ordered, versioned, human-readable rule set
  with configurable thresholds.
- **FR-007**: The outcome MUST be one of APPROVE, SOFT_DECLINE or NEEDS_HUMAN_REVIEW. There is no
  automated hard decline.
- **FR-008**: NEEDS_HUMAN_REVIEW MUST be chosen when any cross-check fails, any document is
  unreadable, income per member is in the borderline band, credit shows active defaults or a poor
  score, or the work history is unstable. SOFT_DECLINE MUST be chosen when none of those apply and
  income per member is above the band or net wealth is above the limit. Otherwise APPROVE.
- **FR-009**: Every outcome MUST include all reasons that applied, each citing the value, the
  threshold and the source document; SOFT_DECLINE MUST include at least one next step.
- **FR-010**: Each submitted application MUST be stored with its form, the original documents, the
  extracted values, the cross-check results, the eligibility values derived from them (for example
  income per member and net wealth), the outcome, the reasons and the rule version, append only (as
  in feature 001).
- **FR-011**: NEEDS_HUMAN_REVIEW cases MUST appear in the existing caseworker review queue with
  their reasons.
- **FR-012**: Economic enablement recommendations MUST be produced only by a locally hosted language
  model, from an anonymised profile with no name, Emirates ID or exact income, in three sections:
  training/upskilling, job matching, career counselling.
- **FR-013**: If the model is unavailable, times out (configurable, default 90 s) or returns an
  unusable answer, a fixed fallback recommendation MUST be shown and labelled as such. Enablement
  MUST never change the outcome.
- **FR-014**: A single command MUST generate the three demo packs reproducibly, each with five
  documents and its form values, and each MUST produce its intended outcome.
- **FR-015**: Logs MUST NOT contain names, Emirates IDs or incomes (as in feature 001).
- **FR-016**: When the character recognition on the ID card reports a confidence below a
  configurable threshold (default 0.80) for a required field, the ID card MUST be treated as
  unreadable, so the case goes to NEEDS_HUMAN_REVIEW with that reason.
- **FR-017**: Each document reading and each language-model call MUST be recorded against the
  application with its inputs, its outputs and how long it took; the anonymised profile sent to the
  model is stored with the plan.

### Key Entities

- **Application**: the form values, reference number and submission time (existing).
- **Uploaded Document**: one of the five types, the original file, whether it was read successfully.
- **Extracted Value**: field name, value, source document.
- **Cross-check Result**: check name, form value, document value, passed or failed.
- **Decision**: outcome, reasons (each with value, threshold, source), next steps, rule version
  (extends the existing assessment result).
- **Enablement Plan**: training items, job matches, counselling note, whether it is a fallback.
- **Demo Pack**: intended outcome, five documents, form values.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the three demo packs produces its intended outcome on every run (3 of 3).
- **SC-002**: From pressing submit, the decision with reasons is shown in under 30 seconds on the
  demo laptop; enablement recommendations follow within a further 90 seconds or the fallback shows.
- **SC-003**: For the three demo packs, every field used in the decision is extracted correctly
  compared with the pack's answer key.
- **SC-004**: Every reason shown names its source document; no outcome is shown without reasons.
- **SC-005**: A presenter can run the whole demo (three applications plus the caseworker queue) in
  under 10 minutes following the README.

## Assumptions

- Documents are those produced by the existing synthetic generator; the extractors only need to
  handle that known layout, not arbitrary real-world documents.
- Family size comes from the form; documents are not required to show it, so no family-size
  cross-check is required for the demo.
- Thresholds reuse the 002 labelling policy where they exist: borderline band 2,000–2,500 AED per
  member, net wealth limit 500,000 AED, poor credit score below 550, unstable work below 12 of the
  last 24 months.
- No address check is done in this feature.
- The new document-based assessment serves applications submitted with documents. The 001 form-only
  submission stays available to programmatic clients only (the 002 seeding command) with its
  configured placeholder assessor; the applicant UI always requires the five documents (FR-002).
- Out of scope now: agent orchestration, ML classifier, tracing/observability tooling, vector store,
  chat, draft previews of extracted values before submission, strict compliance.
- The demo runs on the Windows CPU laptop with the local model already pulled.
