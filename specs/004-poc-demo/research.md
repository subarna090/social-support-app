# Research: PoC Demo (004)

## R1 PDF text extraction

- **Decision**: `pypdf` `extract_text()`, then line-based regex per document type.
- **Rationale**: tested on a 002 pack (2026-10-26). Labels and values come out on clean lines, for
  example `Account holder: …`, `Total credits: 9,900.00 AED. Closing balance: …`, `Score: 663 (range
  300-900)`, `Active defaults: 0`, and resume job lines `Title, Employer (Sep 2021 - Present)`.
  Credit-report table cells come out one per line (`Name` and then the value on the next line). The
  library is pure Python and already in the lock file (dev group).
- **Alternatives**: pdfplumber (heavier, not needed for this layout); an LLM (excluded by the user).

## R2 ID card OCR

- **Decision**: `rapidocr-onnxruntime` 1.4.4, with one engine created lazily and reused.
- **Rationale**: tested on a 002 card: 1.2 s to load and 2.8 s per card, every field read correctly at
  0.96–1.0 confidence. Its models ship in the wheel, so it works offline (the newer `rapidocr` 3.x
  downloads models on first run). OCR sometimes drops spaces in captions (`ExpiryDate`), so the
  parser matches captions with spaces removed, finds the value as the next line, and matches the ID
  number with the regex `784-\d{4}-\d{7}-\d`.
- **Confidence routing** (Principle III): each extracted ID card field keeps the line's OCR score. If
  a required field (name, ID number, date of birth) scores below `OCR_MIN_CONFIDENCE` (default 0.80;
  the test card scored 0.96–1.0), the card is `ok=False` with the error "read with low confidence",
  which routes the case to review.
- **Alternatives**: Tesseract (cannot be installed here); EasyOCR (PyTorch, too heavy); vision LLMs
  (slow on CPU, excluded).

## R3 Income definition

- **Decision**: monthly income = the average of the statement's `Total credits` lines (all sources:
  salary, business, rental, pension, benefits). The cross-check compares it with the form's declared
  net monthly income at a tolerance of `INCOME_TOLERANCE_PCT` (default 10%).
- **Rationale**: matches the 001/002 definition of `net_monthly_income_aed` (all household sources).

## R4 Months employed and as-of date

- **Decision**: parse resume job ranges (`Mon YYYY - Mon YYYY|Present`) and compute months employed
  in the 24 full months before the credit report's issue date, using the same algorithm as
  `synthetic.profile.months_employed_last_24` (reimplemented in extraction, which must not import
  synthetic). Years of experience = the sum of job lengths.
- **Rationale**: a date taken from the documents keeps results deterministic; "today" is never used.

## R5 Decision rules: all findings, worst outcome wins

- **Decision**: add `LabellingPolicy.evaluate_all(facts)`, which returns every non-default rule whose
  conditions hold, in file order. A new `decision_v1.toml` holds self-contained rules (each rule
  repeats its own bounds) with outcomes APPROVE (positive findings), SOFT_DECLINE or
  NEEDS_HUMAN_REVIEW. The outcome is the most severe finding: NEEDS_HUMAN_REVIEW > SOFT_DECLINE >
  APPROVE. Cross-check failures and unreadable documents become review findings in code, outside the
  TOML.
- **Rationale**: the spec requires all reasons and "review wins over soft decline". This reuses the
  002 parser, the reason templates and content-hash versioning. The 002 first-match evaluator and
  `eligibility_v1.toml` are unchanged.
- **Thresholds**: approve when income per member < 2000, net wealth ≤ 500 000, credit score ≥ 550 with
  0 defaults, and (≥ 12 of 24 months worked or not in work). Review when income per member is
  2000–2500, there is ≥ 1 default, the score is < 550, or the applicant is working with < 12 months.
  Soft decline when income per member > 2500 or net wealth > 500 000.
- **Alternatives**: keep first-match (reports only one reason); hard-code rules in Python (not
  versioned or readable).

## R6 Inputs for the eligibility facts

- **Decision**: `HouseholdFacts` from family size and employment status (form) plus documents: income
  (bank), assets and liabilities (spreadsheet), score and defaults (credit report), months employed
  (resume). If any of these documents failed to extract, the rules are skipped and the outcome is
  review, with one finding per failed document.
- **Identity boundary**: the service, not the assessor, builds `HouseholdFacts` (with source labels)
  and turns failed cross-checks and unreadable documents into review findings. The assessor's
  signature is `assess_case(facts: HouseholdFacts | None, findings: tuple[Finding, ...]) ->
  CaseAssessment`, so it never receives documents, names or ID numbers (the CLAUDE.md rule that
  assessors never see identity). The facts used are stored in `decision_inputs` (Principle IV).

## R7 Enablement via Ollama

- **Decision**: call `POST {OLLAMA_URL}/api/chat` with `format: "json"`, `stream: false`, temperature
  0.3, model `ENABLEMENT_MODEL` (default `qwen2.5:7b`), and an httpx timeout of `ENABLEMENT_TIMEOUT_S`
  (default 90). The prompt holds the anonymised profile and asks for
  `{"training": [...], "job_matches": [...], "career_counselling": "..."}`. The answer is validated
  (three keys, non-empty lists of strings, at most 5 items each); anything else becomes the fallback
  plan.
- **Profile sent**: skills, education (university and graduation year), years of experience, last
  job title, employment status, months employed in the last 24, family size, outcome and an income
  band label ("below support band", "borderline", "above band"). No name, ID, employer, exact
  income, nationality or gender.
- **Rationale**: no SDK (Principle VI, an `EnablementAdvisor` protocol). JSON mode makes qwen2.5
  output parseable. A separate endpoint keeps the decision fast (spec SC-002). The plan is stored
  append-only, together with the exact profile sent and the call's `latency_ms` (Principle VII); a
  repeat call returns the stored plan instead of calling the model again.
- **Alternatives**: the `ollama` Python package (an extra dependency for one call); streaming
  (unnecessary for the demo).

## R8 Demo packs

- **Decision**: `synthetic/demo.py` builds three `HouseholdProfile`s by hand with fixed names and IDs
  (pack indexes 901–903), as of 2026-10-01, and renders them with `build_pack` and `write_pack`, so
  each pack has form.json and answer_key.json like any 002 pack.
  - **approve**: family 5, salary 6 000 AED (Sales Associate, 20+ months), net wealth about 30 000,
    score 720, 0 defaults → 1 200 per member.
  - **soft_decline**: family 2, salary 18 000 (Project Manager), property worth 750 000 → 9 000 per
    member, net wealth over 500 000.
  - **review**: family 4, income 9 000 (2 250 per member, borderline), and the form declares 7 000
    (the 002 `INCOME_MISMATCH` injection pattern, applied with a fixed value).
- **Rationale**: hand-built values make the presenter's story exact. Reusing the renderers keeps the
  documents identical in layout to the generator's.

## R9 Upload handling

- **Decision**: multipart fields `bank_statement`, `emirates_id_card`, `resume`, `assets_liabilities`,
  `credit_report`. A missing field gives a 422 in the flat `errors` shape naming the document. A file
  over 10 MB, empty, or of the wrong type (checked by magic bytes: `%PDF`, PNG/JPEG, `PK` zip for xlsx)
  is stored, marked FAILED with the reason, and routes the case to review (spec edge cases).
- **Rationale**: matches the spec; magic bytes are more reliable than browser content types.
