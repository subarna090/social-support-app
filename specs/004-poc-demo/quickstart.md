# Quickstart: PoC Demo (004)

## Prerequisites
- `uv sync`
- Ollama running, with `qwen2.5:7b` pulled (`ollama list`)
- `.env` with `CASEWORKER_PASSCODE` set (see `.env.example`; new optional keys: `UPLOAD_DIR`,
  `INCOME_TOLERANCE_PCT`, `OLLAMA_URL`, `ENABLEMENT_MODEL`, `ENABLEMENT_TIMEOUT_S`)

## Run

```powershell
uv run social-support-data demo                     # writes data/demo/{approve,soft_decline,review}
uv run uvicorn social_support.api.main:app          # terminal 1
uv run streamlit run src/social_support/ui/app.py   # terminal 2
```

## Validation scenarios

| # | Do | Expect |
|---|---|---|
| 1 | Apply tab: enter `data/demo/approve/form.json` values, attach its 5 files, submit | APPROVE; one positive reason each for income per member, wealth, credit and employment; all 4 cross-checks pass; extracted values listed per document; within 30 s |
| 2 | Wait under the decision | Enablement plan in three sections that mention the resume's skills or role, labelled with the model name |
| 3 | Same with `data/demo/soft_decline` | SOFT_DECLINE; reasons cite income per member above 2500 and net wealth above 500 000; next steps shown |
| 4 | Same with `data/demo/review` | NEEDS_HUMAN_REVIEW; reasons: borderline income 2250.00, and declared income vs bank income mismatch |
| 5 | Review queue tab, passcode | The review case is listed with both reasons |
| 6 | Stop Ollama, submit the approve pack again | Same APPROVE and reasons; enablement shows the labelled fallback |
| 7 | Submit with a PDF in the ID card slot | NEEDS_HUMAN_REVIEW, reason names the ID card as unreadable |

## Automated

```powershell
uv run pytest                                            # includes the 3-pack end-to-end test (real OCR, fake LLM)
uv run pytest tests/e2e/test_demo_packs_end_to_end.py
```
