# Quickstart: Document Extraction

A validation guide and demo script that prove feature 003 works end to end. Endpoints are in
[contracts/api.md](./contracts/api.md), commands in [contracts/cli.md](./contracts/cli.md), fields
in [contracts/field-catalogue.md](./contracts/field-catalogue.md), and entities in
[data-model.md](./data-model.md).

## Prerequisites

- `uv sync` has been run. It now installs `rapidocr_onnxruntime` and `pypdf`.
- Ollama is running locally with `qwen2.5:7b` pulled (`ollama list`). No other network access is
  needed.
- `.env` sets `CASEWORKER_PASSCODE`. The new settings have working defaults (`.env.example`):
  `OLLAMA_BASE_URL`, `EXTRACTION_LLM_MODEL=qwen2.5:7b`, `EXTRACTION_CONFIDENCE_THRESHOLD=0.80`,
  `DRAFT_TTL_HOURS=24`, `MAX_DOCUMENT_MB=10`.

## 1. Run the tests

```powershell
uv run pytest                       # default suite: fake OCR/LLM, real PDF/xlsx parsers (no models needed)
uv run pytest -m models             # real RapidOCR + Ollama on generated packs (skipped if unavailable)
uv run pytest -m "slow and models"  # 20-pack accuracy run: SC-001, SC-002, SC-009
```

## 2. Prepare the demo data (once, before the demo)

```powershell
uv run social-support-data generate --count 20 --seed 3 --inconsistency-rate 30
uv run social-support-extract broken-samples --out data/demo/broken
```

The first command creates a fresh run, `data/synthetic/s3-n20-<hash>/`. Runs generated before
2026-10-24 19:35 lack monthly balances in their answer keys, so use a fresh run. In its
`summary.csv`, note one pack with no inconsistency and the packs whose `inconsistency_types` is
`INCOME_MISMATCH`, `IDENTITY_MISMATCH` or `FAMILY_SIZE_MISMATCH`. If a type is missing, generate
again with another seed.

The second command writes `truncated.pdf`, `empty.pdf`, `spreadsheet-as-id.png`, `oversized.pdf`
and `no-text.pdf` to `data/demo/broken/`.

## 3. Start the app

```powershell
uv run uvicorn social_support.api.main:app        # API, docs at http://127.0.0.1:8000/docs
uv run streamlit run src/social_support/ui/app.py # UI at http://localhost:8501
```

Expected: `GET /api/v1/health` reports `"extraction": {"ocr": "ready", "llm": "ready", …}` within
about 20 seconds of startup, once the OCR engine has warmed up.

Start the accuracy report now in a third terminal, so it finishes during the demo (step 10).

## 4. Demo script (about 10 minutes)

Use the **Apply** tab. Each pack's files are in
`data/synthetic/<run>/packs/pack-NNNN/`, and the values to type are in its `form.json`.

| # | Action | Expected | Covers |
|---|---|---|---|
| 1 | Attach a clean pack's five files, then start typing the form from `form.json` | Each document shows *Waiting → Reading → Read* while you type. All five are read within 2 minutes; expect about 30 s | US2-1, FR-008, SC-003 |
| 2 | Before the credit report is attached, press **Submit** | Refused: "Attach the missing documents: Credit report." Nothing is stored | US2-7, FR-012 |
| 3 | Attach the last document and press **Submit** straight away | Refused: "Wait until all documents have been read." | US2-6, FR-012 |
| 4 | Expand **What we read from your documents** | Values grouped by document, read-only (no inputs). Each shows its document; uncertain values are marked | US1-1/2/3, US2-2/4, FR-009 |
| 5 | Submit the clean pack | Recommendation and reference number, the same as in 001 for those form values | US2-5 |
| 6 | New application: an `INCOME_MISMATCH` pack. Type the form's (lower) income | **Net monthly household income** is highlighted, with the bank statement's total shown next to it. Submit still works | FR-010, FR-011, SC-007 |
| 7 | New application: an `IDENTITY_MISMATCH` pack | **Full name** or **Emirates ID** is highlighted against the ID card | FR-010 |
| 8 | New application: attach `data/demo/broken/truncated.pdf` as the resume and `spreadsheet-as-id.png` as the ID card, plus a pack's other three documents | Both documents fail, each with a plain reason. The other three are read. Submit gives **Needs Human Review**, with flag reason "extraction: resume failed; ID card failed" | US3-1/3, FR-018, FR-019 |
| 9 | Restart the API with `EXTRACTION_CONFIDENCE_THRESHOLD=0.99`, then submit a clean pack | The ID card name (OCR score 0.96–0.98) is uncertain, which is a routing field, so the outcome is **Needs Human Review**. Restore 0.80 afterwards | US3-2/3, FR-004 |
| 10 | **Review queue** tab, enter the passcode | Steps 8 and 9 are listed with their extraction reasons | US3-3 |
| 11 | **Open application** with step 8's reference | The form values next to the extracted values, the failed documents with reasons, uncertainty flags, and download buttons for the originals | US3-5, FR-020 |
| 12 | **Open application** with step 5's reference (an approved case) | The same view, for a case that never went to review | US3-6, FR-020 |
| 13 | Show the accuracy report started in step 3 | Per document type and field: matched, mismatched, not found and rate; the mismatching packs; method versions. Text-based documents ≥ 95% and ID card ≥ 90%, finished in under 15 minutes | US4, SC-001/002/009 |

Reloading the page in the middle of an application starts a fresh, empty form (Clarification
2026-10-25). The abandoned draft is deleted after 24 hours.

## 5. Accuracy report (US4)

```powershell
uv run social-support-extract accuracy --run data/synthetic/<run>
uv run social-support-extract accuracy --run data/synthetic/<run> --out data/reports/extraction/rerun
```

Expected:
- The first run prints the summary table and writes `extraction-accuracy.json` and `.md`.
- The re-run gives identical figures (compare the `fields` arrays; only `created_at` and `timing`
  differ). That is SC-008.
- For a pack with `ADDRESS_MISMATCH`, the credit report's stale address counts as a **match**,
  because it is what the document shows (US4-2).

Spot-check 3 packs by hand (the US4 independent test):

```powershell
uv run social-support-extract pack data/synthetic/<run>/packs/pack-0001
```

Compare its values with that pack's `answer_key.json → documents`.

## 6. Storage, audit and privacy checks

- **Append-only** (FR-016): `uv run pytest tests/unit/test_architecture.py`. `ApplicationRepository`
  still has only add and get methods.
- **Originals unchanged**: download a document in the caseworker view, then compare its SHA-256
  with the pack file (`Get-FileHash`).
- **Method versions** (FR-017): the caseworker view's extraction block, and the `extraction_results`
  table, show the method id, the versions and the threshold for each document.
- **Logs** (FR-021): search the API's stderr for a pack's name, Emirates ID or income. There should
  be no match. Logs show `draft_ref`, `document_type`, `extraction_status` and timings only.
- **Every submission needs documents** (FR-013): `POST /api/v1/applications` without a `draft_id`
  returns 422 (`/docs` → *Try it out*).
- **Expiry** (FR-014): `uv run pytest -k draft_expiry`. That test advances the clock past 24 hours
  and checks that the draft, its documents and their contents are gone.

## 7. Seeding with documents (FR-025)

```powershell
uv run social-support-data seed --run data/synthetic/<run> --limit 5
```

Expected: each pack is submitted with its five documents, taking about 30 s per pack while
extraction runs. `seeding_report.csv` shows `extraction_status = read` for clean packs. Packs whose
`expected_routing` was driven only by an inconsistency are **not** routed by extraction. Judging
those is feature 004.
