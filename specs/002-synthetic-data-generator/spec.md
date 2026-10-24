# Feature Specification: Synthetic Applicant Data Generator

**Feature Branch**: `002-synthetic-data-generator`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Generate synthetic applicant packs for testing and demos: form data plus matching mock documents (bank statement, Emirates ID image, resume, assets/liabilities Excel, credit report), with controllable inconsistencies (e.g. income mismatch, address mismatch) and labelled expected outcomes, so later features (extraction, validation, ML) have realistic data without any real personal information."

## Clarifications

### Session 2026-10-24

- Q: How should the labelling policy combine income per member, employment history, net wealth and credit standing into one expected outcome? → A: An ordered list of named rules evaluated top to bottom; the first rule that matches decides the outcome, and the answer key records which rule fired.
- Q: Should a pack with an injected inconsistency keep its profile-based eligibility label and carry "route to review" as a separate second label, rather than having its single label overwritten with Needs Human Review? → A: Yes, two labels: an eligibility outcome from the true profile (the outcome mix applies to it) and an expected routing that is Needs Human Review when the pack has an inconsistency and otherwise equals the eligibility outcome.
- Q: Should the answer key record only each document field's expected value, or also where it appears on the page or image? → A: Values only: for each document, every field name with its expected value; no page or position data.
- Q: How should people run the generator and the seeding step: only from a terminal command, or also from a screen in the demo app? → A: Terminal command only; generation, inconsistency injection, dataset export and seeding are options of one command, with no application screen or API endpoint for them in this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a reproducible batch of consistent applicant packs (Priority: P1)

A developer or tester asks for a batch of applicant packs, choosing how many and a seed number.
Each pack describes one fictional household: the application form details plus the five
supporting documents an applicant would attach (bank statement, Emirates ID card image, resume,
assets and liabilities spreadsheet, credit report). Every document in a pack tells the same story
as the form. Each pack comes with an answer key that records the true values behind the documents
and the outcome the household should receive. Running the same request again with the same seed
produces exactly the same packs.

**Why this priority**: every later feature needs this data. Document extraction needs documents
to read and true values to check itself against; validation needs packs that are known to be
consistent; the eligibility model needs labelled examples. Without reproducibility, tests and
demos cannot rely on the data.

**Independent Test**: generate a small batch, open each document of one pack and confirm it is
readable and agrees with the form and the answer key; generate again with the same seed and
confirm the output is identical.

**Acceptance Scenarios**:

1. **Given** no previous output, **When** the user requests 10 packs with seed 42, **Then** 10
   packs are produced, each containing form details, the five documents, and an answer key.
2. **Given** a generated pack, **When** a reviewer opens its documents, **Then** the name,
   Emirates ID, address, family members, income and employment shown agree with the form and with
   the answer key.
3. **Given** a batch generated with seed 42, **When** the user generates again with the same count,
   seed and settings, **Then** the content of every pack is identical to the first run.
4. **Given** a batch generated with seed 42, **When** the user generates with seed 43, **Then** the
   packs differ.
5. **Given** any generated document, **When** it is viewed, **Then** it is visibly marked as
   synthetic and does not reproduce the branding of any real government body, bank or credit
   bureau.

---

### User Story 2 - Inject controlled cross-document inconsistencies (Priority: P2)

A tester asks for a batch in which a chosen share of packs contain deliberate inconsistencies of
chosen types, for example the income on the form differs from the salary credits on the bank
statement, or the address on the form differs from the one on the credit report. The answer key
of every pack lists exactly which inconsistencies were injected, in which documents, with the
true and the altered values. Packs without injected inconsistencies remain fully consistent.

**Why this priority**: the brief requires the system to detect inconsistencies across documents,
and the constitution requires generators to produce them deliberately. Validation (feature 004)
can only be measured against packs whose inconsistencies are known.

**Independent Test**: generate a batch with a 30% inconsistency rate limited to income mismatches;
confirm that the listed packs, and only those, show a different income between form and bank
statement, and that the answer key records the true and the altered values.

**Acceptance Scenarios**:

1. **Given** a request for 100 packs with a 30% inconsistency rate, **When** generation finishes,
   **Then** 30 packs carry at least one injected inconsistency and 70 carry none.
2. **Given** a request restricted to address mismatches, **When** generation finishes, **Then**
   every injected inconsistency is an address mismatch between form and credit report.
3. **Given** a pack with an injected inconsistency, **When** its answer key is read, **Then** it
   names the inconsistency type, the documents involved, the true value and the altered value.
4. **Given** a pack whose answer key lists no inconsistencies, **When** its documents are compared
   with each other and with the form, **Then** no differences are found.
5. **Given** a pack with an injected inconsistency, **When** its answer key is read, **Then** its
   expected routing is Needs Human Review and its eligibility outcome is the one its true household
   profile earns under the labelling policy, unchanged by the inconsistency.

---

### User Story 3 - Export a labelled dataset for model training (Priority: P3)

A data scientist asks for a large batch together with a single table that summarises every pack:
one row per household with its characteristics (income, family size, employment history, wealth,
liabilities, credit standing), its eligibility outcome and its expected routing. They can control
the mix of eligibility outcomes so that the eligibility model (feature 005) has enough examples of each.

**Why this priority**: the scikit-learn classifier required by the brief needs a labelled training
set. A summary table avoids every consumer re-reading thousands of documents.

**Independent Test**: generate 500 packs with a requested outcome mix, then confirm that the
summary table has 500 rows, that each row matches its pack's answer key, and that the outcome mix
is within the stated tolerance.

**Acceptance Scenarios**:

1. **Given** a request for 500 packs, **When** generation finishes, **Then** a summary table with
   500 rows is produced alongside the packs, one row per pack, linked by pack identifier.
2. **Given** a requested outcome mix of 40% Approve, 40% Soft Decline and 20% Needs Human Review,
   **When** 500 packs are generated, **Then** each outcome's share is within 5 percentage points of
   the request.
3. **Given** the summary table, **When** a row is compared with its pack's answer key, **Then** all
   values agree.
4. **Given** the summary table, **When** its columns are inspected, **Then** protected attributes
   (nationality, gender, religion, ethnicity, marital status) are either absent or clearly marked as
   not for use as model inputs.

---

### User Story 4 - Seed the running application with generated applicants (Priority: P4)

A presenter preparing a demo sends the form details of a generated batch into the running
application through its normal submission path, so the review queue and lookups contain realistic
applicants. A short report shows, per pack, the reference number received and whether the
application's recommendation matched the pack's eligibility outcome.

**Why this priority**: useful for demos and for checking the end-to-end path at volume, but not
needed by the later data-consuming features, which read the packs directly.

**Independent Test**: start the application, seed it with 20 generated packs, then look up three
of the returned reference numbers with their Emirates IDs and confirm the details match the packs.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** the presenter seeds 20 packs, **Then** 20
   applications are submitted and the report lists 20 reference numbers.
2. **Given** a seeded pack, **When** its reference number and Emirates ID are looked up, **Then**
   the stored details equal the pack's form details.
3. **Given** the application is not running, **When** the presenter tries to seed, **Then** a clear
   message says the application cannot be reached and nothing is reported as submitted.

---

### Edge Cases

- A count of zero, a negative count, or a count above the supported maximum is rejected with a
  clear message before anything is written.
- Inconsistency rate or outcome mix values outside 0–100%, or an outcome mix that does not add up
  to 100%, are rejected with a clear message.
- Generating into a location that already holds output never silently mixes old and new packs: the
  user must choose a new location or explicitly allow replacement.
- A single-member household (no dependants) and a large household (10 or more members) are both
  supported and appear in batches.
- Households with zero income (unemployed, no benefits) and households with income only from
  non-salary sources (rental, pension, business) are supported; the bank statement then shows the
  corresponding credits, or none.
- An inconsistency type that does not apply to a pack (for example "employer mismatch" for a
  household with no employment) is never injected into that pack.
- When a requested outcome mix cannot be met exactly because of rounding, the difference is at most
  one pack per outcome.

## Requirements *(mandatory)*

### Functional Requirements

**Packs and documents**

- **FR-001**: System MUST generate a requested number of applicant packs, each with a unique pack
  identifier, from a count and a seed supplied by the user.
- **FR-002**: Each pack MUST contain the application form details: full name, Emirates ID number,
  address, contact details, family size and family members (name, relationship, age),
  net monthly household income, and employment status. The fields that the existing application
  form accepts MUST be valid for submission to it.
- **FR-003**: Each pack MUST contain five documents that a person can open and read: a bank
  statement covering at least three months of transactions, an Emirates ID card image (front side),
  a resume with employment history, an assets and liabilities spreadsheet, and a credit report with
  a credit score, open obligations and the household members on file.
- **FR-004**: Unless an inconsistency was injected, every value that appears in more than one place
  (form and documents) MUST agree, including name, Emirates ID, date of birth, address, employer,
  monthly income and family members.
- **FR-005**: Each pack MUST include a machine-readable answer key holding the true household
  profile, the expected value of every field shown in every document (field name and value per
  document; positions on the page or image are not recorded), the list of injected
  inconsistencies (possibly empty), the eligibility outcome with its reason, and the expected
  routing.
- **FR-006**: Given the same count, seed and settings, generation MUST produce identical content;
  different seeds MUST produce different packs.

**Inconsistencies**

- **FR-007**: Users MUST be able to set the share of packs that contain injected inconsistencies
  (0–100%) and restrict which inconsistency types are used.
- **FR-008**: The generator MUST support at least these inconsistency types: income mismatch (form
  vs bank statement), address mismatch (form vs credit report), family size mismatch (form vs
  the household members listed on the credit report), name or Emirates ID mismatch (form vs ID card image), and employment
  mismatch (form vs resume).
- **FR-009**: For each injected inconsistency the answer key MUST record its type, the documents
  involved, the true value and the altered value. No inconsistency may exist in a pack that is not
  recorded in its answer key.

**Labels and dataset**

- **FR-010**: Every pack MUST carry an eligibility outcome (Approve, Soft Decline, or Needs Human
  Review) derived from its true household profile by a documented, versioned eligibility labelling
  policy that weighs income per family member, employment history, net wealth (assets minus
  liabilities) and credit standing. The policy MUST be an ordered list of named rules evaluated top
  to bottom, where the first matching rule decides the outcome and a final default rule always
  matches. Each rule MUST state its factors and thresholds, and the answer key MUST name the rule
  that fired and the values it compared.
- **FR-011**: Every pack MUST also carry an expected routing: Needs Human Review, with the
  inconsistencies named as the reason, when the pack contains any injected inconsistency (in line
  with the human-in-the-loop principle for unresolved cross-document conflicts); otherwise equal to
  the eligibility outcome. Injecting an inconsistency MUST NOT change the eligibility outcome.
- **FR-012**: Neither the eligibility outcome nor the expected routing may depend on nationality, gender, religion, ethnicity or
  marital status. Packs MAY carry such attributes to make documents realistic.
- **FR-013**: Users MUST be able to request an outcome mix (shares of each eligibility outcome) and
  the generator MUST meet it, independently of the inconsistency rate, within 5 percentage points for batches of 500 or more.
- **FR-014**: Each batch MUST include a summary table with one row per pack, holding the pack
  identifier, the household characteristics used for labelling, the count and types of injected
  inconsistencies, the eligibility outcome, the rule that decided it, and the expected routing.
- **FR-015**: Each batch MUST include a run record stating the count, seed, settings, generation
  date, the version of the generator and of the labelling policy, and the outcome and inconsistency
  counts actually produced.

**Privacy and safety**

- **FR-016**: All people, employers, banks, addresses and numbers MUST be fictional. Emirates ID
  numbers MUST follow the format the application accepts (784-YYYY-NNNNNNN-N) and be drawn from a
  documented block reserved for synthetic data, so a generated number can be recognised as
  synthetic.
- **FR-017**: Every document MUST carry a visible "SYNTHETIC – NOT A REAL DOCUMENT" marking and
  MUST NOT copy the logos, layouts or names of real government bodies, banks or credit bureaus.
- **FR-018**: Generated output MUST be written only to a local location chosen by the user and MUST
  be excluded from version control by default.

**Seeding the application**

- **FR-019**: Users MUST be able to submit the form details of a generated batch to the running
  application through its normal submission path and receive a report of reference numbers,
  returned outcomes and whether each matched the pack's eligibility outcome.
- **FR-020**: If the application cannot be reached, seeding MUST stop with a clear message and MUST
  NOT report any pack as submitted that was not.

**Interface**

- **FR-021**: All capabilities of this feature (generation, inconsistency injection, dataset export
  and seeding) MUST be available through a single command run from a terminal, with its settings
  given as options. This feature MUST NOT add a screen to the application's UI or an endpoint to
  its API; seeding uses only the existing submission path.

### Key Entities *(include if feature involves data)*

- **Household Profile**: the true, fictional facts about one applicant household: identity,
  address, family members, employment history, income sources, assets, liabilities, credit
  standing. All documents in a pack are rendered from it.
- **Applicant Pack**: one household's form details, its five documents and its answer key,
  identified by a pack identifier.
- **Document**: one generated file of a given type (bank statement, Emirates ID image, resume,
  assets and liabilities spreadsheet, credit report), belonging to one pack.
- **Inconsistency**: a deliberate difference injected into a pack: type, documents involved, true
  value, altered value.
- **Answer Key**: the ground truth for one pack: profile, expected document field values,
  inconsistencies, eligibility outcome with the deciding rule, and expected routing.
- **Generation Run**: one invocation: count, seed, settings, versions, produced counts; owns the
  packs and the summary table.
- **Labelling Policy**: the documented, versioned, ordered list of named rules (first match wins)
  that turns a household profile into an eligibility outcome and a reason; its version is recorded in every run record and answer key.
- **Summary Table**: one row per pack for model training and analysis.
- **Seeding Report**: per pack, the reference number received from the application, the returned
  outcome and whether it matched.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A batch of 100 complete packs is generated in under 5 minutes on the reference laptop
  (CPU only, no network access needed).
- **SC-002**: Re-running with the same count, seed and settings produces identical content for 100%
  of packs.
- **SC-003**: In packs without injected inconsistencies, 100% of cross-document values agree with
  the answer key, verified automatically over a batch of at least 200 packs.
- **SC-004**: 100% of injected inconsistencies appear in the answer key, and 0 unlisted
  differences are found, verified automatically over a batch of at least 200 packs.
- **SC-005**: For batches of 500 or more, each eligibility outcome's share is within 5 percentage
  points of the requested mix.
- **SC-006**: 100% of generated documents carry the synthetic marking, and 100% of generated
  Emirates ID numbers fall within the documented synthetic block.
- **SC-007**: A new team member can generate a demo batch and open a pack's documents in under 10
  minutes by following the README.
- **SC-008**: When 50 packs are seeded into the running application, 100% are accepted with a
  reference number, and the report's match / no-match flag is correct for every pack.

## Assumptions

- Users of this feature are developers, testers, data scientists and demo presenters on the team;
  applicants never use it.
- Users run the feature from a terminal; a "Demo data" screen in the application is out of scope
  for this feature and may come with a later one.
- Document text is in English. Arabic text on documents is out of scope for this feature.
- The Emirates ID image shows the front side only, as a clearly fictional mock card. Optional scan
  effects (slight rotation, blur, noise) to exercise OCR are a nice-to-have, off by default.
- Bank statements cover three to six months; currency is AED throughout.
- A batch of up to 5,000 packs is enough for training and evaluating the eligibility model;
  larger batches are out of scope.
- The existing application accepts only name, Emirates ID, family size, net monthly income and
  employment status, so seeding (User Story 4) submits only those fields; the documents are not
  uploaded, since document upload arrives in feature 003.
- The seeding report's match rate is informative, not a pass/fail check: the application's current
  placeholder rule sees only three household attributes, so it can legitimately disagree with the
  eligibility outcome. Once the ML or agent assessor arrives, this rate becomes an evaluation metric.
- Generated output lives on the local machine only and is never committed, consistent with the
  local-first and privacy principles.
