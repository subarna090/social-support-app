# Feature Specification: Document Extraction

**Feature Branch**: `003-document-extraction`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Feature 003 document extraction". Elaborated from the roadmap: extract structured fields from an applicant's documents (bank statement, resume and credit report PDFs, Emirates ID card image, assets/liabilities spreadsheet) using locally run tools only; store each raw document with its extracted fields; record which document every value came from; measure field-level accuracy against the feature 002 answer keys; route failed or low-confidence extraction to human review. Scope decisions (2026-10-24): documents are attached in the application itself, extraction runs in the background, and the applicant sees the extracted values before submitting the form. The extracted values are read-only: they show that the right documents were uploaded and help the applicant spot typos in the form; the applicant can edit only the form fields.

## Clarifications

### Session 2026-10-25

- Q: Should an application submitted with no documents at all still get an automated recommendation, or go to human review? → A: Neither: all five documents are mandatory. Submission is refused until a document of every type is attached; the form-only path ends with this feature.
- Q: How many generated packs should the accuracy report be required to cover? → A: As few as needed, so it is fast enough to run during a demo: 20 packs by default, with the batch size configurable for larger optional runs.
- Q: Should any uncertain extracted value send the application to human review, even one that plays no part in the decision or the form comparison? → A: No. Only uncertain routing fields (the values shown next to a form field, plus the ID card's name, ID number and date of birth) route the case; other uncertain values are flagged for the caseworker but do not route. Failed documents always route.
- Q: Where should broken documents for testing and the demo come from? → A: A small fixed set of hand-made broken files (truncated PDF, empty file, spreadsheet declared as the ID card image, file over 10 MB) kept with the tests and reused for the demo; the feature 002 generator is unchanged.
- Q: Which submitted applications can a caseworker open to see documents and extracted values? → A: Those in the review queue, plus any submitted application opened by its reference number, behind the same caseworker passcode.
- Q: If the applicant reloads or closes the page before submitting, can they resume the draft? → A: No. Reloading or closing starts a fresh form; the abandoned draft is left for the 24-hour deletion.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract the fields of an applicant's documents (Priority: P1)

The system reads an applicant's five documents (bank statement, Emirates ID card image, resume,
assets and liabilities spreadsheet, and credit report) and produces each document's fields as
structured values: for example the account holder, monthly income credits and closing balances from
the bank statement, or the name, ID number and date of birth from the ID card. Every value says
which document it came from and how confident the system is in it. The original documents are kept,
unchanged, next to the extracted values.

**Why this priority**: every other story in this feature, and every later feature, depends on
structured values instead of files. Cross-document validation (004) compares extracted values with
the form, the eligibility model (005) and the agents (006) assess them, and explanations must trace
back to documents (Constitution II).

**Independent Test**: run extraction on one generated pack from feature 002 and compare the
extracted values of each document with that pack's answer key.

**Acceptance Scenarios**:

1. **Given** the five documents of one applicant, **When** extraction runs, **Then** each document
   has a set of extracted fields, each with a value (or "not found"), its source document and a
   confidence level.
2. **Given** a bank statement, **When** it is extracted, **Then** the account holder, address,
   statement period, each monthly income credit and each month's closing balance are extracted.
3. **Given** an Emirates ID card image, **When** it is extracted, **Then** the name, ID number,
   nationality, date of birth, sex and expiry date are extracted.
4. **Given** an extracted value, **When** a reviewer asks where it came from, **Then** the system
   names the source document and can show the original document unchanged.
5. **Given** a document that does not contain a field (for example a resume with no current job),
   **When** it is extracted, **Then** that field is reported as "not found" and no value is invented.

---

### User Story 2 - Attach documents while applying and check what was read (Priority: P2)

While filling in the application form, the applicant attaches the five documents. Extraction starts
in the background, and the applicant can keep filling in the form; the form shows that the
documents are being read. When extraction finishes, the applicant sees what was read from each
document, with uncertain values highlighted, before submitting. This view is read-only: it lets
the applicant confirm that they uploaded the right documents. Where the documents cover a form
field (name, Emirates ID, family size, net monthly household income, employment status), the
document's value is shown next to the form field, and a difference is highlighted so the applicant
can fix a typo in what they entered. The applicant can change only the form fields, never the
extracted values; if a document was read wrongly or the wrong file was attached, they can replace
the document. On submission, the documents and the extraction result are stored with the
application, and the applicant gets their recommendation and reference number as before.

**Why this priority**: this is the end-to-end path the brief asks for (an interactive form with
attachments). Showing the applicant what was read lets them catch a wrong upload or a typo in the
form before a decision is made, while keeping the documents' values out of the applicant's hands.

**Independent Test**: in the app, attach the five documents of a generated pack, type a different
income in the form, wait for the extracted values to appear, confirm the difference is highlighted
and the extracted values cannot be edited, fix the form, submit, then confirm the stored application
holds the documents and the extracted values.

**Acceptance Scenarios**:

1. **Given** an applicant filling in the form, **When** they attach the five documents, **Then**
   extraction starts and the form shows its progress while the applicant keeps filling in fields.
2. **Given** extraction has finished, **When** the applicant views the result, **Then** each
   document's extracted values are listed, uncertain values are highlighted, and failed documents
   show a plain reason.
3. **Given** extracted values that cover form fields, **When** the applicant views the form,
   **Then** each covered field shows the document's value next to what the applicant entered, and
   fields where the two differ are highlighted.
4. **Given** the extracted values, **When** the applicant tries to change one, **Then** they cannot;
   they can only change the form fields or replace the document.
5. **Given** extraction has finished, **When** the applicant submits, **Then** the application is
   stored with its documents and extraction result, and the applicant sees the recommendation and
   reference number. Differences between form and documents do not block submission.
6. **Given** extraction has not finished yet, **When** the applicant tries to submit, **Then** they
   are told to wait for the documents to be read, and nothing is submitted.
7. **Given** fewer than five documents are attached, **When** the applicant tries to submit,
   **Then** submission is refused, the missing document types are named, and nothing is submitted.

---

### User Story 3 - Route failed or uncertain extraction to human review (Priority: P3)

When a document cannot be read (corrupt file, wrong type, protected, empty) or a field's confidence
is below the configured threshold, the system does not continue as if the value were known. The
document or field is flagged with a plain reason and the other documents are still processed. If a
document failed or a routing field (one the form is checked against, or an identity field) is
uncertain, the submitted application goes to the caseworker review queue with the extraction
reasons listed; other uncertain values are flagged for the caseworker without routing the case.
Caseworkers can open the application to see its documents, the extracted values, uncertainty flags
and the form values the applicant submitted.

**Why this priority**: the constitution requires failed extraction to go to human review
(Principle III); silent failures would let later decisions rest on wrong or missing values.

**Independent Test**: submit an application where one document is corrupted and one field is
uncertain, then confirm both are flagged with reasons, the application appears in the review queue
with those reasons, and the caseworker can see the extracted values and the original documents.

**Acceptance Scenarios**:

1. **Given** a corrupted, empty or wrong-type document, **When** extraction runs, **Then** that
   document is recorded as failed with a reason and the other documents are still extracted.
2. **Given** a field whose confidence is below the threshold, **When** extraction completes,
   **Then** the field is flagged as uncertain, with its value kept for the reviewer.
3. **Given** a submitted application whose extraction has any failed document or uncertain routing
   field, **When** it is assessed, **Then** its recommendation is Needs Human Review and the review
   queue shows the extraction reasons.
4. **Given** a submitted application whose only uncertain values are not routing fields (for
   example a resume's education entry), **When** it is assessed, **Then** the recommendation is
   made as before and the uncertain values stay flagged for a caseworker who opens it.
5. **Given** a submitted application with documents, **When** a caseworker with the passcode opens
   it, **Then** they see each document, its extracted values and uncertainty flags next to the
   form values the applicant submitted.
6. **Given** an automatically approved or soft-declined application, **When** a caseworker with the
   passcode enters its reference number, **Then** they see the same documents and extracted values
   view as for a queued case.

---

### User Story 4 - Measure extraction accuracy against known answers (Priority: P4)

A developer runs extraction over a batch of generated packs and gets an accuracy report: for each
document type and each field, the share of values that match the answer key, plus the list of
mismatches by pack. The report states which extraction methods and versions produced it, so two
reports can be compared after a change.

**Why this priority**: without a measured accuracy there is no way to know whether decisions rest on
correct data, or whether a change made extraction better or worse. Feature 002 created the answer
keys for exactly this purpose.

**Independent Test**: run the accuracy report over 20 generated packs and confirm its per-field
figures agree with a manual comparison of three packs.

**Acceptance Scenarios**:

1. **Given** a batch of generated packs, **When** the accuracy report runs, **Then** it shows, for
   each document type and field, how many values matched, how many differed and how many were not
   found.
2. **Given** a pack with an injected inconsistency (for example a stale address on the credit
   report), **When** it is evaluated, **Then** extraction is judged against what that document
   actually shows, so a correctly extracted altered value counts as a match.
3. **Given** two values that differ only in formatting (thousands separators, letter case,
   surrounding spaces, date notation), **When** they are compared, **Then** they count as a match.
4. **Given** the same batch and the same extraction version, **When** the report runs twice,
   **Then** the figures are identical.

---

### Edge Cases

- A file of the wrong kind for its declared type (for example a spreadsheet attached as the ID
  card) fails that document with a clear reason.
- A password-protected, corrupted or empty file fails that document; the others continue.
- An applicant who has attached fewer than five documents cannot submit; the missing types are
  named. This includes an applicant who attaches none: the form-only path ends with this feature.
- An attached document that fails to be read (for example a corrupted file) still counts as
  attached: the applicant may replace it or submit anyway, and the application goes to human
  review.
- An applicant replaces a document before submitting: the new file is read and its values replace
  the earlier ones in the form view; only the final documents and their extraction are stored with
  the application.
- An applicant leaves without submitting: the attached documents and their extraction results are
  deleted after 24 hours.
- An applicant reloads or closes the page before submitting: the draft cannot be resumed. A fresh,
  empty form starts, and the earlier draft is left for the 24-hour deletion.
- A multi-page bank statement is read in full, including transactions that continue on later pages.
- A field present more than once in a document (for example several income credits in one month)
  is extracted as a list, not reduced to one value.
- A document larger than 10 MB is rejected with a clear reason before it is read.
- Text that is not in English, handwriting, and photographed or scanned paper documents are out of
  scope; such documents are expected to come out as uncertain or failed rather than wrong.

## Requirements *(mandatory)*

### Functional Requirements

**Extraction**

- **FR-001**: The system MUST accept, for one application, up to one document of each type: bank
  statement, Emirates ID card image, resume, assets and liabilities spreadsheet, and credit report.
  The document type is declared by whoever provides the document.
- **FR-002**: The system MUST extract, at minimum, these fields:
  - Bank statement: account holder, address, statement period, each income credit (description
    and amount), each month's closing balance, and the total monthly income credits.
  - Emirates ID card: name, ID number, nationality, date of birth, sex, expiry date.
  - Resume: name, email, phone, address, current employer (or none), employment history (employer,
    title, start and end month), education.
  - Assets and liabilities: each asset (type and value), each liability (type, lender, outstanding
    balance, monthly payment), total assets, total liabilities, net wealth.
  - Credit report: name, ID number, date of birth, address on file, household members (name,
    relationship, age), credit score, number of active defaults, accounts (lender, type, balance,
    status).
- **FR-003**: Every extracted value MUST record its source document, so any value used later can be
  traced to the document it came from (Constitution II).
- **FR-004**: Every extracted value MUST carry a confidence level. Values below a configurable
  threshold MUST be flagged as uncertain (Constitution III: thresholds are explicit, configurable
  values).
- **FR-005**: A field that does not appear in a document MUST be reported as "not found". For
  text-based documents, every extracted value MUST appear in the document's own text; the system
  MUST NOT report values it cannot find in the document.
- **FR-006**: All reading and extraction MUST run on the local machine. No document, page image,
  text or extracted value may be sent to an external service (Constitution I).

**Applying with documents**

- **FR-007**: Applicants MUST be able to attach documents to the application form before
  submitting, and to replace or remove an attached document before submitting.
- **FR-008**: Extraction MUST start automatically once a document is attached and run in the
  background; the applicant MUST be able to keep filling in the form and MUST see whether each
  document is waiting, being read, read, or failed.
- **FR-009**: Before submitting, the applicant MUST be able to see every extracted value grouped by
  document, with uncertain values highlighted and failed documents explained. Extracted values MUST
  be read-only for the applicant.
- **FR-010**: For each form field that a document covers (full name and Emirates ID from the ID
  card, family size from the credit report's household members, net monthly household income from
  the bank statement, employment status from the resume), the form MUST show the document's value
  next to the field and highlight the field when the two differ, ignoring formatting differences.
  The document's value MUST NOT be copied into the form automatically.
- **FR-011**: The applicant MUST be able to change only the form fields. To change what a document
  says, the applicant MUST replace the document. Differences between the form and the documents
  MUST NOT block submission (judging them is feature 004's job).
- **FR-012**: Submission MUST be refused, with a clear message, until a document of each of the five
  types is attached, naming the missing types, and while any attached document is still waiting or
  being read. Submission MUST be allowed once all five are attached and each is read or failed.
- **FR-013**: On submission, the documents and the extraction result MUST be stored with the
  application and linked to its reference number. Applications without all five documents MUST NOT
  be accepted by any submission path, including direct calls to the application's interface.
- **FR-014**: Attached documents and extraction results of applications that are never submitted
  MUST be deleted 24 hours after they were attached.
- **FR-015**: Only the applicant's own form session may see its attached documents and extracted
  values before submission. After submission, only caseworkers with the caseworker passcode may
  view an application's documents and extracted values.

**Storage, audit and review**

- **FR-016**: The system MUST keep each original document unchanged alongside its extracted values.
  After submission, documents and extraction results are append-only.
- **FR-017**: Every extraction result MUST record which extraction method and version produced
  each document's values, and when, so results can be compared and replayed (Constitution IV).
- **FR-018**: A document that cannot be read (wrong type, corrupted, protected, empty, or over
  10 MB) MUST be recorded as failed with a plain reason without stopping the other documents.
- **FR-019**: A submitted application whose extraction has any failed document or uncertain
  routing field MUST receive the recommendation Needs Human Review, with the extraction reasons as
  its flag reason, and appear in the review queue (Constitution III). Routing fields are the
  document values compared with the form under FR-010 (full name, Emirates ID, family size, net
  monthly household income, employment status) plus the ID card's name, ID number and date of
  birth. Uncertain values in other fields MUST stay flagged but MUST NOT change the
  recommendation, which is otherwise made exactly as before this feature.
- **FR-020**: Caseworkers with the passcode MUST be able to open any submitted application, either
  from the review queue or by entering its reference number, whatever its recommendation, and see
  its documents, extracted values and uncertainty flags next to the form values the applicant
  submitted. An unknown reference number gives a plain "not found".
- **FR-021**: Logs MUST NOT contain document contents or extracted personal values (names, ID
  numbers, incomes); they may contain identifiers, document types, statuses and counts.

**Accuracy evaluation**

- **FR-022**: Users MUST be able to run extraction over a batch of feature 002 packs and produce an
  accuracy report: for each document type and field, the number of matches, mismatches and "not
  found" results, the match rate, and the list of mismatching packs. The default batch is 20 packs;
  the batch size MUST be configurable for larger runs.
- **FR-023**: Comparison MUST judge each document against what that document shows (the answer
  key's per-document values), ignoring formatting differences: thousands separators, currency
  labels, letter case, repeated or surrounding spaces, and date notation.
- **FR-024**: The accuracy report MUST record the extraction methods and versions, the batch it was
  run on and the run date, and MUST give identical figures when re-run on the same batch with the
  same versions.

**Existing paths affected**

- **FR-025**: Feature 002's seeding MUST submit each generated pack's five documents together with
  its form details, so seeded applications satisfy FR-012. Feature 001 behaviour that relied on
  form-only submission (its tests and demo script) MUST be updated to attach documents.

### Key Entities *(include if feature involves data)*

- **Document**: one file attached to an application: declared type, the original file kept
  unchanged, size, and status (waiting, being read, read, failed).
- **Extraction Result**: one run of extraction over a document: when, with which method version,
  the outcome (read, or failed with reason), and its extracted fields.
- **Extracted Field**: one value from one document: field name, value (or "not found"), source
  document, confidence level, uncertain flag, and whether it is a routing field (FR-019).
- **Draft Application**: the applicant's form session before submission, holding attached
  documents and extraction results; it lives only as long as that session (it cannot be resumed
  after a reload) and is deleted after 24 hours if never submitted.
- **Accuracy Report**: the evaluation of one batch: per document type and field, matches,
  mismatches, "not found" counts and match rate; mismatching packs; versions and batch used.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the default batch of 20 generated packs, at least 95% of fields from the bank
  statement, resume, assets and liabilities spreadsheet and credit report match the answer key.
- **SC-002**: On the same batch, at least 90% of ID card fields match the answer key.
- **SC-009**: The default 20-pack accuracy report finishes in under 15 minutes on the reference
  laptop, so it can be run live during a demo.
- **SC-003**: After an applicant attaches all five documents, the extracted values are shown within
  2 minutes on the reference laptop (CPU only, no network).
- **SC-004**: An applicant can attach five documents, check the extracted values against the form,
  fix a typo in the form and submit in under 10 minutes.
- **SC-005**: 100% of extracted values name their source document, and for text-based documents 0
  extracted values are absent from the document's own text.
- **SC-006**: 100% of failed documents and uncertain fields are flagged with a reason, every
  application with a failed document or an uncertain routing field is routed to human review, 0
  applications are routed for uncertain non-routing fields alone, and 0 applications are accepted
  without all five documents.
- **SC-007**: In 100% of cases where a covered form field differs from its document's value, the
  difference is highlighted to the applicant before submission, and 0 extracted values can be
  changed by the applicant.
- **SC-008**: Re-running the accuracy report on the same batch with the same versions gives
  identical figures in 100% of runs.

## Assumptions

- Documents follow the formats produced by feature 002: English text, text-based PDFs (not scans),
  an unrotated card image without blur, and a spreadsheet with labelled sheets. Real-world layouts,
  scans, photographs, handwriting and Arabic text are out of scope; such documents are expected to
  be flagged as uncertain or failed rather than read correctly.
- Because the documents come from one generator, high accuracy on them does not prove accuracy on
  other layouts. The accuracy report states the batch it was measured on.
- The 20-pack default trades statistical confidence for speed: fields that appear only on some
  documents (for example a current employer) get few examples. Larger batches can be run
  unattended when a more reliable figure is needed.
- Unreadable documents (FR-018) are exercised with a small fixed set of hand-made broken files: a
  truncated PDF, an empty file, a spreadsheet declared as the ID card image and a file over 10 MB.
  They are kept with the tests and reused in the demo. The feature 002 generator only produces
  readable documents and is not changed for this, so the accuracy report is measured on readable
  packs only.
- Each application has at most one document of each type; several bank statements per applicant
  are out of scope.
- All five documents are mandatory from this feature on. Feature 001's form-only submission ends;
  its tests and demo, and feature 002's seeding, move to submissions with documents (FR-025).
- Highlighting form-versus-document differences here is a typing aid for the applicant, not a
  verdict. Recording and judging discrepancies, and deciding whether they matter, is feature 004's
  job.
- The recommendation rule from feature 001 is unchanged, except that applications with extraction
  problems are routed to Needs Human Review (FR-019). It still uses the form's values; using
  extracted values in decisions comes with features 004-006.
- Background extraction runs on the same laptop as the application; a few applicants at a time is
  enough for the PoC. The 2-minute target (SC-003) assumes one applicant's documents at a time.
- A draft application is identified by an unguessable identifier held by the applicant's form
  session; there are still no applicant accounts or logins.
