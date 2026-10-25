# Research: Document Extraction

Decisions for feature 003. Each one records what was chosen, why, and what was rejected. The user
fixed RapidOCR for the ID card image and the local `qwen2.5` models through Ollama. Timings below
were measured on the reference laptop (Windows 11, CPU only) on 2026-10-25 against feature 002
packs.

---

## R1. Package layout and layering

**Decision**: one new layer, `social_support/extraction/`, beside `assessment/`. The pure contract
lives in `domain/extraction.py`: `DocumentType`, `ExtractedField`, `DocumentExtraction`, the
`DocumentExtractor` protocol and a `build_extractors(settings)` factory that imports the
implementations lazily, the same pattern as `build_assessor`. `extraction/` holds the five
extractors, the PDF-text, OCR and LLM adapters, the field catalogue, the comparison rules and the
accuracy evaluation with its CLI.

Import rules, enforced in `tests/unit/test_architecture.py`:

- `extraction` may import `domain`, `config` and `services.tracing` (logging only). It must not
  import `persistence`, `services.applications`, `api`, `ui`, `synthetic` or `assessment`.
- `domain` still imports no framework; `domain/extraction.py` uses only the standard library.
- `api` and `ui` still must not import `synthetic`. `ui` still talks only to the API.
- The accuracy evaluation reads feature 002 pack folders through the published pack format
  (`specs/002-synthetic-data-generator/contracts/pack-format.md`), never by importing `synthetic`.

**Rationale**: extraction is an extension point like assessment: later features (004 validation,
006 agents) consume `DocumentExtraction` values, never parser internals. Keeping vendor libraries
(pypdf, RapidOCR, openpyxl, httpx for Ollama) inside `extraction/` adapters satisfies
Constitution VI: services depend on the protocol only.

**Alternatives considered**: putting extraction inside `services/`. Rejected: services orchestrate
use cases and must stay testable without models. Putting it in `synthetic/`: rejected, because
extraction is part of the application, not the data generator.

## R2. Reading PDF text

**Decision**: `pypdf` (already a dev dependency, promoted to runtime) `extract_text()` on every
page. Lines equal to the synthetic marking or matching `Page N` are dropped before parsing, so
multi-page statements read as one stream. The cleaned text is kept per document and is the
reference for the grounding rule (R9).

Measured: with reportlab's table layout, pypdf emits one table cell per line (for example
`2026-06-01` / `Salary - Gulf Breeze Facilities (Demo)` / `5,950.00` / `32,690.00`). Reading
takes milliseconds per document.

**Rationale**: pure Python with no native install, and it handles the generator's text-based PDFs
exactly. A PDF without extractable text (a scan, or a protected file) yields no text, so the
document fails with a plain reason (FR-018) instead of being guessed.

**Alternatives considered**: `pdfplumber` (better table geometry, but adds pdfminer and is slower;
the cell-per-line output already suffices). PyMuPDF (fast, but AGPL licence). An LLM over the whole
PDF text: rejected for structured documents, as it would be slower and could invent values.

## R3. Bank statement and credit report: layout parsers

**Decision**: deterministic, label-anchored parsers over the cleaned text.

- **Bank statement**: header lines by label (`Account holder:`, `Address:`, `Statement period:`,
  `Opening balance:`). Transactions are runs of date, description, amount and balance lines. A cell
  with one amount is ambiguous between the credit and debit columns, so the parser decides using the
  running balance: if `previous balance + amount = balance` it is a credit, if `previous - amount`
  it is a debit. If neither holds, the transaction is kept and marked uncertain (confidence 0.5).
  Each month's `Total credits: … Closing balance: …` line gives the monthly totals, and those are
  cross-checked against the transactions. **Income credits** are the credit transactions.
- **Credit report**: label/value pairs for the subject (`Name`, `Emirates ID`, `Date of birth`,
  `Address on file`). Household member rows are read as triplets of name, relationship (one of the
  known relationship words) and age. `Score: N`, `Active defaults: N`, and account rows (lender,
  type, balance, status).

**Rationale**: these documents are tables, so a parser is exact, explainable and fast. The
running-balance rule recovers the column information that text extraction loses, and it also
checks itself.

**Alternatives considered**: LLM extraction for these documents (slow on CPU, see R5, and it can
invent numbers), and template coordinates (fragile when a statement runs onto a second page).

## R4. Assets and liabilities spreadsheet

**Decision**: `openpyxl` (already a runtime dependency) in read-only mode. The parser finds the
sheets `Assets`, `Liabilities` and `Summary` by title and the header row by its labels, then reads
the data rows. Totals are read from `Summary` and cross-checked against the sums of the rows. A
total that disagrees with its rows is kept and marked uncertain.

**Rationale**: the spreadsheet is already structured, so parsing it is exact. A file that is not a
valid xlsx, or that lacks a labelled sheet, fails with a reason.

**Alternatives considered**: pandas `read_excel` (adds nothing over openpyxl here and hides cell
types).

## R5. Resume: local LLM for the less structured sections

**Decision**: a hybrid extractor.

- **Contact block** (name, email, phone, address): read deterministically. The name is the first
  content line, then the email and phone are matched by pattern, and the address is the following
  line.
- **Employment history and education**: the text between the `Employment history` and `Skills`
  headings goes to **`qwen2.5:7b`** through the Ollama HTTP API, with `temperature 0`, a fixed
  `seed` and `keep_alive` set so the model stays loaded. The prompt asks for a **compact
  line protocol** instead of JSON:

  ```text
  JOB | employer | title | start | end
  EDU | institution | graduation year
  ```

  The parser then validates every line (R9): each value must appear in the section text, and dates
  must be `Mon YYYY` or `Present`. **Current employer** is derived as the job whose end is
  `Present`, or none. **Employment status** for the form comparison is derived as "currently
  working" if there is a current job, otherwise "not currently working".

Measured on generated resumes:

| Variant | Time per resume | Correct |
|---|---|---|
| 7b, full-resume JSON schema (pretty-printed) | 55–84 s | yes |
| 3b, full-resume JSON schema | ~42 s | no: missed the current employer |
| 7b, sliced sections, JSON schema | 27–62 s | no: one resume returned "No employment history." as a job |
| 3b, sliced sections, JSON schema | 32–38 s | no: the watermark came back as a job, and a job was invented from the education line |
| **7b, sliced sections, line protocol** | **13–25 s** | **yes, 5 of 5** |

The line protocol cuts the output tokens 3–4×, because pretty-printed JSON spends most of its
tokens on whitespace and keys, and CPU generation runs at about 3–5 tokens per second.

**Rationale**: the brief asks for a local LLM for less structured text, and the resume's free-form
job lines are the right place for it. Contact fields have universal patterns, so using the LLM for
them would add time and risk with no benefit. Grounding (R9) keeps the LLM from inventing values.

**Fallback**: there is no automatic fall-back to `qwen2.5:3b`, which was measurably unreliable on
this task. If Ollama is unreachable or times out (`EXTRACTION_LLM_TIMEOUT_S`, default 120), the
resume is recorded as failed ("the language model is unavailable"), and the application goes to
human review (FR-018, FR-019).

**Alternatives considered**: a pure regex resume parser (fast, but it would leave no LLM in the
pipeline and not reflect real resume variety). Using the LLM for every field (slower, and more
chances to invent values). Ollama's JSON-schema `format` (measured above: slower and no more
accurate).

## R6. Emirates ID card image: RapidOCR

**Decision**: `rapidocr_onnxruntime` (ONNX, CPU, installed with pip). The card image is
**upscaled 2×** (Lanczos) before OCR. Values are paired with labels by geometry: for each known
label (`Name`, `ID Number`, `Nationality`, `Date of Birth`, `Sex`, `Expiry Date`, compared without
spaces because OCR drops some), the value is the nearest text box directly below it, in the same
column. The OCR engine loads once per process, lazily, and is warmed up in the background when the
API starts (about 13 s).

Measured: about 3–5 s per card at 1×. Full names matched the answer key in 18 of 20 cards at 1×;
the two misses lost a space (`SalemAl Suwaidi`, `MaryWilliams`). At 2×, 20 of 20 matched. Line
scores were 0.96–1.00.

**Format checks**:
- The ID number must match `784-YYYY-NNNNNNN-N` and pass the Luhn check.
- Dates must parse as ISO dates.
- Sex must be `M` or `F`.

A value that fails a check gets confidence 0.5, and so is uncertain (R8).

**Rationale**: the user's choice, and measurably accurate on the generated cards. Label geometry
needs no layout coordinates, so it tolerates small layout shifts.

**Alternatives considered**: Tesseract (cannot be installed here), EasyOCR (PyTorch, too heavy),
and vision LLMs (slow on CPU, and they can invent text).

## R7. Field catalogue and naming

**Decision**: a single catalogue (`extraction/catalogue.py`, documented in
[contracts/field-catalogue.md](./contracts/field-catalogue.md)) lists, for each document type:

- every field path (for example `bank_statement.income_credits[2].amount_aed`)
- its value kind (text, money, date, month, integer, enum)
- the answer-key path it is scored against
- whether it is a **routing field** (FR-019)
- whether it feeds a **covered form field** (FR-010)

List-valued fields use indexed paths in document order. The accuracy report groups them by their
index-free form (`income_credits[].amount_aed`).

**Rationale**: one source of truth drives the extractors' output shape, the routing gate, the form
comparison and the accuracy scoring, so the four cannot drift apart.

## R8. Confidence and the uncertainty threshold

**Decision**: every value carries a confidence from 0 to 1, and a value is **uncertain** when its
confidence is below `EXTRACTION_CONFIDENCE_THRESHOLD` (default **0.80**; Constitution III):

| Source | Confidence |
|---|---|
| Parser or spreadsheet value that matched its label and passed its checks | 1.00 |
| Parser value whose cross-check failed (running balance, monthly total, sheet total) | 0.50 |
| OCR value | the OCR line score; 0.50 if a format check fails |
| LLM value, grounded verbatim and well-formed (R9) | 0.90 |
| Value derived from LLM values (current employer, employment status) | the lowest confidence among its inputs; 0.50 if any LLM line was rejected |
| "Not found" | no confidence; reported as not found (FR-005) |

**Rationale**: these scores are simple, explainable and testable. Ollama returns no token
probabilities here, so the LLM's confidence comes from verification (grounding plus format), not
from the model's self-assessment. Rejecting an LLM line lowers the confidence of the employment
status, which is a routing field, so a doubtful resume reaches a caseworker.

**Demo lever**: the threshold is a setting. Raising it to `0.99` makes OCR names (0.96–0.98)
uncertain, which gives a repeatable "uncertain routing field" case (quickstart step 9).

## R9. Grounding: no invented values (FR-005, SC-005)

**Decision**: for text-based documents (PDFs), every extracted value must appear in the document's
cleaned text after normalisation (R10): case-folded, whitespace collapsed, thousands separators
removed. Values written in a different form are re-rendered in the document's own form before the
check, for example a month written `Oct 2026`, or `Present` for a null end date. An LLM line whose
values are not all grounded is rejected, and its count is recorded in the extraction result's
warnings. A unit test asserts the rule over every PDF value in a batch, which is the SC-005 check.

The ID card is an image, so grounding does not apply; its values come straight from OCR text boxes.
The spreadsheet's values are cell values, so they are grounded by construction.

## R10. Normalisation for comparison (FR-010, FR-023)

**Decision**: one pure module, `domain/normalise.py`, used by both the form comparison and the
accuracy scoring. Two values are equal when their canonical forms are equal:

| Kind | Canonical form |
|---|---|
| text | Unicode NFKC, case-folded, runs of whitespace collapsed, trimmed |
| money | `Decimal`, with currency labels (`AED`) and thousands separators removed, quantised to 2 dp |
| date | ISO `YYYY-MM-DD`; also accepts `DD/MM/YYYY` and `D Mon YYYY` |
| month | `YYYY-MM`; accepts `Mon YYYY`, `Month YYYY` and ISO dates |
| Emirates ID | 15 digits, with dashes and spaces removed |

**Rationale**: it lives in `domain` because both the application (comparison) and the evaluation
need it, and it has no dependencies.

## R11. Background extraction and progress

**Decision**: extraction runs **in the API process** on a `ThreadPoolExecutor` owned by the app
(created in the lifespan, `EXTRACTION_WORKERS`, default 1). Each attached document is queued as
one job. The job reads the stored bytes, runs the extractor and writes the result back to the
draft.

- A document's status moves through `WAITING → READING → READ | FAILED`.
- Replacing a document bumps a per-slot `generation` counter, and a job whose generation is stale
  discards its result.
- On startup, any draft documents left in `WAITING` or `READING` (the server stopped mid-job) are
  marked `FAILED` with the reason "reading was interrupted; replace the document".

One worker is the right size: the LLM and OCR are CPU-bound, so parallel jobs would only slow each
other. Expected time for one applicant's five documents is about 25–35 s: resume 13–25 s, ID card
about 6 s at 2×, and the others under 1 s. That is well inside SC-003 (2 minutes).

**Rationale**: no extra service or broker (Constitution VIII), and it works with `uvicorn` on
Windows. The executor sits behind a small `ExtractionQueue` class, so a real queue (Celery, RQ)
could replace it later.

**Alternatives considered**:
- FastAPI `BackgroundTasks`: runs after the response on the request's worker thread pool, with no
  concurrency limit and no cancellation; rejected.
- A separate worker process: more moving parts for a single-laptop PoC.
- Extracting inside the UI process: rejected, because the UI must only talk to the API.

## R12. Drafts: identity, storage and expiry

**Decision**:

- `POST /api/v1/drafts` creates a draft whose id is `secrets.token_urlsafe(32)`. The id is the only
  credential: the UI keeps it in `st.session_state`, so a page reload starts a new draft
  (Clarification, 2026-10-25). Draft ids are never logged; logs carry a short SHA-256 prefix
  (`draft_ref`) instead.
- Draft tables are **mutable**: documents can be replaced or removed, and statuses and results
  change. They live in their own `DraftRepository`. The append-only rule (001 FR-009) still holds
  for every submitted-application table. The architecture test is extended to check that
  `ApplicationRepository` still has no update or delete methods.
- **Expiry**: a draft expires 24 hours after it was created (`DRAFT_TTL_HOURS`). An asyncio task in
  the lifespan deletes expired drafts every 15 minutes, and also once at startup. A document
  attached later than the draft's creation still expires with the draft. The spec says "24 hours
  after they were attached"; measuring from the draft's creation is equal or earlier, which is
  stricter for privacy.
- **Size limit**: uploads are read in chunks and stopped at 10 MB + 1 byte. An oversized file is
  recorded as `FAILED` ("larger than 10 MB") with its name and size but no content, so it still
  counts as attached, but nothing oversized is stored (FR-018 edge case).
- **File type**: decided from the leading bytes, never from the filename:
  - `%PDF-` for the bank statement, resume and credit report
  - a PNG or JPEG signature for the ID card
  - an xlsx zip containing `xl/workbook.xml` for the spreadsheet

  A mismatch fails the document: "this file is a spreadsheet, but an ID card image was expected".

## R13. Storing originals with their extraction (multimodal storage)

**Decision**: original bytes are stored **in the database** (`LargeBinary`), in a content table
keyed by SHA-256, which deduplicates identical files. On submission, in the same transaction as the
application and decision rows:

1. The draft's documents become append-only `application_documents`.
2. Their extraction results become `extraction_results`.
3. Their values become `extracted_fields`.

The draft rows are then deleted. Originals are served back to caseworkers byte for byte with their
media type.

**Rationale**: one transaction covers the application, its documents and its extraction, so there
can be no orphan files. It also works the same on SQLite and PostgreSQL (`bytea`), and tests keep
using in-memory SQLite. Files are at most 10 MB, and generated ones are about 2–45 KB.

**Alternatives considered**: a content-addressed folder on disk behind a `DocumentStore`
interface. That is better for large volumes and a natural production step (object storage), but
it adds orphan clean-up and a second thing to back up. It is noted as a future improvement.

## R14. Routing gate for extraction problems (FR-019)

**Decision**: at submission, `ApplicationService` runs an **extraction gate** before the assessor.
If any document failed, or any **routing field** is uncertain, the decision is Needs Human Review:

- `rule_version` is `extraction-gate/v1`, a row added to `assessment_rule_versions` at startup, so
  the decision is auditable (Constitution IV).
- The explanation lists the problems in plain words, for example "The resume could not be read:
  the language model is unavailable. The name on the ID card was read with low confidence."
- `flag_reason` is a short summary, truncated to the 200-character column with "and N more", for
  example "extraction: resume failed; ID card name uncertain".

Otherwise the configured assessor runs exactly as before, on the **form** values (spec
Assumptions). Uncertain non-routing fields never change the outcome; they stay flagged in the
caseworker view.

**Rationale**: it is a separate, versioned rule, so the explanation names it, and the assessors
stay untouched: they still see only family size, income and employment status.

## R15. Form-versus-document comparison (FR-010)

**Decision**: `POST /api/v1/drafts/{id}/comparison` takes the form's current covered values and
returns, for each covered field, the document's value, whether they differ (using R10), and the
document it came from.

| Form field | Document value |
|---|---|
| Full name | ID card name |
| Emirates ID | ID card number |
| Family size | credit report household members **+ 1** (the applicant; in 002 data, `family_size = len(household_members) + 1`) |
| Net monthly household income | the bank statement's total income credits for the **most recent month** |
| Employment status | the resume's derived working status: "currently working" for Employed or Self-employed, "not currently working" for Unemployed, Student or Retired. Self-employment can't be told apart on a resume, so only the category is compared |

The comparison runs on the server, so the UI does not need its own normalisation rules (the UI
talks only to the API). Nothing is copied into the form.

## R16. Streamlit form with live highlighting and progress

**Decision**: the Apply tab drops `st.form`, because inside a form the widget values only reach the
script on submit. Without it, typing or uploading reruns the script, and the comparison updates.

- The five `st.file_uploader` widgets (one per type, with accepted extensions as a hint only) call
  `PUT /drafts/{id}/documents/{type}` in their `on_change` callback.
- A `@st.fragment(run_every=2)` panel polls `GET /drafts/{id}` while any document is `WAITING` or
  `READING`, then stops polling.
- Extracted values are shown read-only (tables and captions, no inputs). Uncertain values get a
  marker, and failed documents show their reason.
- Covered form fields show the document's value under the input, highlighted when they differ.
- The submit button is disabled while documents are missing or still being read, and the missing
  types are named (the server enforces the same rule, FR-012).

The caseworker tab gains an "Open application" lookup by reference number, beside the queue. It
shows the form values, the documents (download buttons for the originals, and an image preview for
the ID card), and the extracted values with confidence and flags.

## R17. Accuracy evaluation (User Story 4)

**Decision**: a new console script, **`social-support-extract`**, with the subcommands `accuracy`,
`pack` and `broken-samples` (see [contracts/cli.md](./contracts/cli.md)).

- `accuracy --run <run folder> [--limit 20]` runs the same extractors as the API over the first N
  packs, in pack order. It scores each catalogue field against `answer_key.documents.<type>`, using
  the R10 rules, and writes `extraction-accuracy.json` and `extraction-accuracy.md` under
  `data/reports/extraction/<run-id>-<timestamp>/`. The report records:
  - the method ids and versions, including the LLM model name and digest
  - the OCR package version
  - the batch (run id, pack ids)
  - the run date
  - the threshold
- `--limit` defaults to 20 (Clarification, 2026-10-24). Expected time is about 20 × 30 s, roughly
  10 minutes, inside SC-009 (15 minutes).

Scoring per field:
- **match**: the values are equal after normalisation
- **mismatch**: a value was extracted but differs
- **not found**: the answer key has a value but extraction reported none
- extracted where the key has none counts as a mismatch

For lists, items are aligned by position. Missing items are "not found" and extra items are
mismatches.

Determinism (SC-008): the parsers and OCR are deterministic. The LLM runs with `temperature 0` and
a fixed seed, against a model pinned by digest, which is recorded in the report. A test with a fake
LLM checks that the scoring itself is deterministic. The quickstart re-runs the live report and
compares the figures.

**Rationale**: a CLI keeps the evaluation out of the request path. It reuses the production
extractors, so the report measures what the app does.

## R18. Broken sample documents (Clarification, 2026-10-25)

**Decision**: `tests/fixtures/broken_documents.py` builds the fixed set in memory, deterministically:

| Sample | How it is built |
|---|---|
| Truncated PDF | the first 600 bytes of a generated resume |
| Empty file | 0 bytes |
| Spreadsheet declared as the ID card | a generated xlsx |
| Over 10 MB | a PDF header followed by 10 MB + 1 byte of padding |
| PDF with no text | a one-page PDF containing only a drawn rectangle |

Building them in memory keeps a 10 MB file out of the repository. `social-support-extract
broken-samples --out data/demo/broken/` writes the same files to disk for the demo. The feature 002
generator is unchanged.

## R19. Seeding moves to documents (FR-025)

**Decision**: `synthetic/seeding.py` now:

1. creates a draft for each pack
2. uploads the pack's five files
3. polls the draft until every document is read or failed (`--wait-timeout`, default 180 s per
   pack)
4. submits the form with the draft id

It still goes only through `ui.client.ApiClient` over HTTP, with the new client methods. The
seeding report gains an `extraction_status` column. Seeding is slower now, because extraction runs
for each pack (about 30 s each), and the README says so. Feature 001's tests and README demo move to
document-backed submissions through a shared test helper. That helper uses fake extractors, so the
default test suite stays fast and needs no models.

## R20. Testing strategy (Constitution V)

**Decision**:

- **Unit, test-first**: normalisation, the running-balance credit/debit rule, every parser on
  stored text fixtures, label geometry on canned OCR boxes, the LLM line protocol and grounding
  with a fake LLM, confidence and threshold, the routing gate, the comparison rules, accuracy
  scoring, and the type checks on leading bytes.
- **Integration (default suite, fake OCR/LLM through `create_app(…, extractors=…)`)**: the draft
  lifecycle, uploads, replacement, the stale-generation discard, submit refusals (missing,
  still reading), storage and append-only checks, the caseworker view and file download, expiry,
  and seeding over in-process HTTP.
- **Integration with real PDFs and spreadsheets**: these parsers need no models, so they run in the
  default suite against packs generated into `tmp_path`.
- **`models` marker (opt-in)**: the real RapidOCR and Ollama extractors on generated packs, plus a
  5-pack accuracy run. They are skipped when RapidOCR or Ollama is not available. The 20-pack
  SC-001, SC-002 and SC-009 run is in `slow` + `models`.
- **End-to-end**: generate one pack, then create a draft, upload, wait, submit, and check the
  caseworker view (fakes in the default suite; real models under `models`).

## R21. Dependencies

**Decision**:

- New runtime: `rapidocr_onnxruntime`, which brings `onnxruntime`, `opencv-python` and `numpy`.
  About 300 MB of RAM while loaded.
- Promoted from dev to runtime: `pypdf`.
- Reused: `httpx`, for the Ollama HTTP API, so the `ollama` SDK is not needed; `openpyxl`;
  `pillow`, for upscaling the card; and `python-multipart`, already installed with FastAPI, for
  uploads.

**Rationale**: pip-only, CPU-only, and no system installs (CLAUDE.md constraints).

## R22. Observability and logging

**Decision**:

- New trace steps on the application trace: `DOCUMENTS_ATTACHED`, `EXTRACTION_CHECKED` (with the
  gate outcome) and, inside each extraction result, per-step timings: text read, OCR, the LLM call
  (model, prompt and output token counts, duration), and parsing.
- New whitelisted log keys: `draft_ref`, `document_type`, `extraction_status`, `method`,
  `duration_ms`, `count`.
- Document text, LLM prompts and outputs, and extracted values are **never** logged (FR-021).
  Prompt and output content tracing is left to feature 008, under its synthetic-data-only rule
  (Constitution I and VII). Constitution VII stays partial, as in 001 and 002 (Complexity
  Tracking).
