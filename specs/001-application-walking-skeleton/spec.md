# Feature Specification: Application Walking Skeleton

**Feature Branch**: `001-application-walking-skeleton`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "A caseworker or applicant submits a social support application through a simple web form (name, Emirates ID number, family size, monthly income, employment status) and immediately sees a recommendation (approve / soft decline / needs human review) with a short explanation. This first slice proves the end-to-end path: form → processing → stored decision → result shown. Document uploads, real ML and multi-agent reasoning come in later features; here the assessment can be a simple placeholder rule, but the decision must be stored and explainable."

## Clarifications

### Session 2026-10-23

- Q: When someone looks up an application by reference number, what must they provide to see its details? → A: Reference number plus the matching Emirates ID; a mismatch returns the same "not found" message as a non-existent reference.
- Q: If the same Emirates ID submits a new application while an earlier one exists, what should happen? → A: Accept it as a separate application with its own reference number; the result notes that a previous application exists. The duplicate does not change the outcome.
- Q: Who should be able to open the caseworker's "Needs Human Review" list when there are no logins? → A: Only someone who enters a single shared caseworker passcode set in configuration; a wrong passcode shows nothing.
- Q: What should "monthly household income" on the form mean? → A: Net (take-home) monthly income from all sources (salary, business, rental, pensions, existing benefits) for all household members, entered as a single field.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Submit an application and see a recommendation (Priority: P1)

An applicant (or a caseworker entering details for them) fills in a short application with their
full name, Emirates ID number, family size, net monthly household income, and employment status,
then submits it. Within a few seconds they see a recommendation (Approve, Soft Decline, or Needs
Human Review) together with a plain-language explanation of why, and a reference number for the
application.

**Why this priority**: this is the entire end-to-end path the walking skeleton exists to prove:
capture, assessment, stored decision, displayed result. Every later feature (document uploads,
validation, ML eligibility, agents, chat) plugs into this path.

**Independent Test**: submit a filled-in application and confirm that a recommendation, an
explanation, and a reference number are shown, and that the outcome matches the placeholder
assessment rule for the values entered.

**Acceptance Scenarios**:

1. **Given** the application form is open, **When** the user submits valid details whose monthly
   income per family member is below the support threshold, **Then** the result shows "Approve",
   an explanation that cites the income-per-member figure and the threshold, and a reference number.
2. **Given** the application form is open, **When** the user submits valid details whose monthly
   income per family member is above the upper limit of the borderline band, **Then** the result shows
   "Soft Decline", an explanation that cites the figures, and at least one suggested next step
   (e.g. reapply if circumstances change, or ask about enablement support).
3. **Given** the application form is open, **When** the user submits valid details whose income per
   member is between the support threshold and the borderline band's upper limit (inclusive), **Then** the result shows "Needs Human Review" with an
   explanation that the case is borderline and will be looked at by a caseworker.
4. **Given** the application form is open, **When** the user leaves a required field empty or enters
   an invalid value (e.g. a malformed Emirates ID, negative income, family size of zero), **Then**
   the application is not submitted and each problem field shows a clear message saying what to fix.

---

### User Story 2 - Look up a previous application's decision (Priority: P2)

An applicant or caseworker enters an application reference number together with the applicant's
Emirates ID and sees the original submitted details, the recommendation, the explanation, and when the decision was made.

**Why this priority**: it proves that decisions are actually stored and can be retrieved
unchanged, which the constitution requires for auditability. It isn't needed to demonstrate the
basic path, so it ranks below P1.

**Independent Test**: submit an application, note its reference number, look it up, and confirm
that the details, outcome, explanation, and timestamp match what was shown at submission.

**Acceptance Scenarios**:

1. **Given** an application was submitted earlier, **When** the user looks it up by its reference
   number and the matching Emirates ID, **Then** the system shows the same details, outcome, and explanation as at submission,
   plus the decision date and time and the version of the assessment rule that was applied.
2. **Given** a reference number that does not exist, **When** the user looks it up, **Then** the
   system shows a "no application found" message and reveals no other applicants' data.
3. **Given** an existing reference number, **When** the user looks it up with an Emirates ID that
   does not match that application, **Then** the system shows the same "no application found"
   message as in scenario 2. It does not reveal that the reference exists.

---

### User Story 3 - Caseworker sees applications awaiting human review (Priority: P3)

A caseworker enters the shared caseworker passcode and opens a list of all applications whose recommendation is "Needs Human Review" and
sees, for each one, the reference number, applicant name, submission time, and the reason it was
flagged.

**Why this priority**: it gives the human-in-the-loop principle a visible destination early,
but the skeleton can be demonstrated without it.

**Independent Test**: submit one borderline and one clear-cut application, open the review list,
and confirm that only the borderline application appears, with its flag reason.

**Acceptance Scenarios**:

1. **Given** several applications with mixed outcomes exist, **When** the caseworker enters the
   correct passcode and opens the review list, **Then** only "Needs Human Review" applications are listed, newest first.
2. **Given** no applications need review, **When** the caseworker opens the review list, **Then**
   an empty-state message is shown.
3. **Given** the review list is requested, **When** the passcode is missing or wrong, **Then** no
   application data is shown and an "access denied" message appears.

---

### Edge Cases

- **Duplicate submission:** the same Emirates ID submits again while an earlier application exists.
  The new application is accepted as a separate record with its own reference number, and the
  result notes that a previous application exists for this ID. Being a duplicate does not
  change the outcome; the earlier application is left unchanged.
- **Extreme values:** very large income or family size (e.g. income above 1,000,000 AED/month or
  family size above 20). These are accepted only within defined upper limits; values outside the
  limits are rejected with a message.
- **Zero income:** this is valid. Income per member is 0, which results in "Approve".
- **Whitespace or formatting:** an Emirates ID entered with or without dashes is accepted and
  stored in one normalised format.
- **Assessment failure:** if the assessment step fails unexpectedly, the application is still
  stored, its outcome is set to "Needs Human Review" with reason "automatic assessment
  unavailable", and the user sees that outcome rather than an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an application form capturing full name, Emirates ID number,
  family size (number of household members including the applicant), total net monthly household
  income in AED (take-home income from all sources: salary, business, rental, pensions and existing
  benefits, for all household members, entered as one figure, with this definition shown to the
  user on the form), and employment status (Employed, Self-employed, Unemployed, Student, Retired).
- **FR-002**: System MUST validate inputs before accepting a submission: all fields required; name
  2–100 characters; Emirates ID in the 15-digit `784-YYYY-NNNNNNN-N` format (dashes optional);
  family size a whole number from 1 to 20; monthly income a number from 0 to 1,000,000 with at most 2 decimal places.
- **FR-003**: System MUST show field-level error messages for every invalid input and MUST NOT
  store invalid submissions.
- **FR-004**: System MUST assign each accepted application a unique, non-guessable reference number
  and show it to the user.
- **FR-005**: System MUST assess each accepted application using the placeholder assessment rule
  (see Assumptions) and produce exactly one outcome: Approve, Soft Decline, or Needs Human Review.
- **FR-006**: System MUST produce, for every outcome, a plain-language explanation that states the
  inputs used, the computed income per family member, the threshold or band compared against, and
  the rule version applied. The exception is when automatic assessment fails (FR-015): then the
  explanation states that assessment was unavailable, that a caseworker will review the
  application, and the rule version `fallback`.
- **FR-007**: System MUST include at least one suggested next step with every Soft Decline outcome.
- **FR-008**: System MUST NOT produce a hard (final) decline automatically.
- **FR-009**: System MUST store each application together with its inputs, outcome, explanation,
  rule version, and decision timestamp, and stored decisions MUST NOT be altered after creation.
- **FR-010**: System MUST show the recommendation and explanation to the user immediately after
  submission, as part of the same interaction, without the user having to look it up separately.
- **FR-011**: Users MUST be able to retrieve an application's stored details and decision by
  providing both its reference number and the matching Emirates ID (normalised the same way as at
  submission). A missing reference and a mismatched Emirates ID MUST produce an identical "no
  application found" response.
- **FR-012**: Caseworkers MUST be able to view a list of applications with outcome "Needs Human
  Review", newest first, showing reference number, name, submission time, and flag reason. Access
  MUST require a single shared caseworker passcode that is set in configuration (not in code). A
  missing or wrong passcode MUST reveal no application data.
- **FR-013**: The assessment rule's threshold and borderline band MUST be adjustable without
  changing the rest of the system, and each change MUST produce a new rule version.
- **FR-014**: System MUST NOT collect protected attributes (nationality, gender, religion,
  ethnicity) in this feature.
- **FR-015**: System MUST route an application to "Needs Human Review" if automatic assessment fails
  for any reason, while still storing the application.
- **FR-016**: System MUST record a processing trace for each application (received, validated,
  assessed, stored, result returned to the user) with timestamps, linked to the reference number.
- **FR-017**: System MUST accept a new application from an Emirates ID that already has one or more
  applications, as a separate record. The result MUST state that a previous application exists,
  but MUST NOT reveal its reference number or details. Duplicate status MUST NOT affect the outcome.

### Key Entities

- **Application**: one submission by or on behalf of an applicant. It holds the reference number,
  full name, normalised Emirates ID, family size, net monthly household income (all sources), employment status, and
  submission timestamp.
- **Decision**: the assessment result for one application. It holds the outcome (Approve / Soft
  Decline / Needs Human Review), explanation, computed income per member, rule version, suggested
  next steps, and decision timestamp. Each application has exactly one decision in this feature.
- **Assessment Rule Version**: a named, versioned set of parameters (income-per-member threshold,
  borderline band upper limit) used to make decisions. Decisions reference the version they used.
- **Processing Trace**: the ordered steps an application went through, with a timestamp and status
  for each step, linked to the application.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can complete and submit the application form in under 2 minutes.
- **SC-002**: The recommendation and explanation are shown within 5 seconds of submission for
  95% of applications on the demo machine.
- **SC-003**: 100% of automatically assessed outcomes include an explanation that names the income-per-member
  figure, the threshold or band, and the rule version.
- **SC-004**: 100% of accepted applications can be retrieved by reference number and Emirates ID with details and
  decision identical to those shown at submission.
- **SC-005**: For a test set of at least 20 synthetic applications covering all three outcomes and
  the boundary values, 100% receive the outcome the placeholder rule predicts.
- **SC-006**: 100% of invalid submissions in a test set covering every validation rule are rejected
  with a field-level message, and none are stored.
- **SC-007**: A reviewer can demonstrate the full path (submit, see result, look up, see review
  list) in under 5 minutes without assistance.

## Assumptions

- **Placeholder assessment rule (v0.1):** compute income per family member as net monthly household
  income divided by family size.
  - **Approve** if income per member is below 2,000 AED.
  - **Needs Human Review** if it is between 2,000 and 2,500 AED inclusive (the borderline band).
  - **Soft Decline** if it is above 2,500 AED.
  - Employment status is captured and shown in the explanation, but it doesn't affect the
    outcome in this version.
  - These figures are illustrative for the PoC, not official policy. Later features replace the
    rule with the ML-based eligibility assessment.
- **Users:** applicants and caseworkers use the same form in this slice. There are no individual
  user accounts. The review list is protected only by a shared caseworker passcode. Proper
  authentication and roles come in a later feature.
- **Data:** synthetic and demo data only, per the constitution. Real personal data is never
  entered.
- **Language and currency:** the interface is English-only, and all amounts are in AED.
- **Out of scope:** document uploads, cross-document validation, ML or agent-based reasoning,
  enablement recommendations, chat, editing or withdrawing applications, and changing a decision
  after a human review. Each of these is covered by a later feature.
- **Reference numbers** are unique and not sequential, so that one application's number doesn't
  reveal how many others exist.
- **Single user:** the system runs locally for a single demo user at a time; concurrent multi-user
  load is out of scope.
