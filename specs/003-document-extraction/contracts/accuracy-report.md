# Accuracy Report Format (`extraction-accuracy/1`)

Written by `social-support-extract accuracy` (see [cli.md](./cli.md)) to
`<out>/extraction-accuracy.json`, with a Markdown rendering in `<out>/extraction-accuracy.md`. Both
are deterministic for the same batch and the same method versions (FR-024, SC-008), apart from
`created_at` and `timing`.

```json
{
  "format": "extraction-accuracy/1",
  "created_at": "2026-10-25T09:15:00Z",
  "run_id": "s42-n20-1a2b3c",
  "pack_ids": ["pack-0001", "…", "pack-0020"],
  "limit": 20,
  "confidence_threshold": "0.80",
  "methods": {
    "BANK_STATEMENT": {"method": "bank-statement-parser/1", "versions": {"pypdf": "6.21.2"}},
    "EMIRATES_ID": {"method": "id-card-ocr/1", "versions": {"rapidocr_onnxruntime": "1.4.4", "scale": "2"}},
    "RESUME": {"method": "resume-llm/1", "versions": {"model": "qwen2.5:7b", "model_digest": "845dbda0ea48", "pypdf": "6.21.2"}},
    "ASSETS_LIABILITIES": {"method": "assets-liabilities-sheet/1", "versions": {"openpyxl": "3.1.5"}},
    "CREDIT_REPORT": {"method": "credit-report-parser/1", "versions": {"pypdf": "6.21.2"}}
  },
  "summary": {
    "text_documents": {"matched": 1418, "total": 1432, "match_rate": "0.990", "target": "0.95", "met": true},
    "id_card": {"matched": 120, "total": 120, "match_rate": "1.000", "target": "0.90", "met": true}
  },
  "documents": [
    {"document_type": "RESUME", "matched": 312, "mismatched": 4, "not_found": 3, "total": 319,
     "match_rate": "0.978", "failed_documents": 0, "uncertain_values": 2}
  ],
  "fields": [
    {"document_type": "RESUME", "field": "jobs[].end", "matched": 30, "mismatched": 1,
     "not_found": 0, "total": 31, "match_rate": "0.968", "mismatching_packs": ["pack-0013"]}
  ],
  "failures": [{"pack_id": "pack-0009", "document_type": "RESUME", "reason": "the language model is unavailable"}],
  "timing": {"total_s": "581.4", "mean_per_pack_s": "29.1", "slowest_step": "resume.llm"}
}
```

Rules:

- `total = matched + mismatched + not_found` for every row. `match_rate = matched / total`, written
  as a 3-dp string (`"0.000"` when the total is 0).
- **Text documents** (SC-001) are the bank statement, resume, assets and liabilities, and credit
  report. **ID card** (SC-002) is the Emirates ID. The derived fields `resume.employment_status`
  and `credit_report.household_size` are reported in `fields` but left out of `summary`, so that
  nothing is counted twice.
- `fields` and `documents` are sorted by document type, then by field path. `mismatching_packs` is
  sorted. This order makes two reports diffable.
- There are no personal values anywhere in the report: only pack ids, field paths and counts.
- The Markdown file has the summary, one table per document type (field, matched, mismatched, not
  found, rate, packs) and the method versions.
