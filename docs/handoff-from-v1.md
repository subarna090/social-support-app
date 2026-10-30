# Handoff from V1 (branch `004-poc-demo`)

Written 2026-10-30 for the team revamp. V1 lives at
https://github.com/subarna090/social-support-app (branch `004-poc-demo`). This note records what
V1 does, what was measured, and the lessons worth carrying into the revamped codebase. Use it to
assess the team version, not as a spec to copy line by line.

## 1. What V1 does

An applicant fills a short form (name, Emirates ID, family size, declared monthly income,
employment status) and uploads five documents. Then:

1. **Extraction, no LLM.** pypdf text and regex for the bank statement, resume and credit report;
   RapidOCR for the Emirates ID image; openpyxl for the assets/liabilities sheet. A document that
   fails to read becomes `ok=False` and never crashes the request.
2. **Four cross-checks**, form against documents: name vs ID card, Emirates ID vs ID card, name vs
   bank account holder, declared income vs average bank credits (10% tolerance).
3. **Rule-based decision** (`decision_v1.toml`). Every rule is judged on its own, every finding is
   kept, and the worst outcome wins: REVIEW > SOFT_DECLINE > APPROVE.
4. **Three outcomes, always with reasons** and the source document of each reason:
   APPROVE, SOFT_DECLINE (with "you may reapply" next steps), NEEDS_HUMAN_REVIEW (goes to a
   passcode-protected caseworker queue with its reasons).
5. **Economic enablement plan from a local LLM** (Ollama `qwen2.5:7b`, JSON mode) built from an
   anonymised profile. If the model fails or times out, a labelled fallback plan is shown and the
   decision is unaffected.

Stack: Python 3.12 (uv), FastAPI, SQLAlchemy 2 on SQLite (append-only tables), Streamlit UI that
talks to the API over HTTP only.

## 2. Decision policy (thresholds)

Income per member = bank-statement average monthly credits / family size (from the form).

| Rule | Outcome | Condition |
|---|---|---|
| income_within_band | APPROVE | income per member < 2000 AED |
| wealth_within_limit | APPROVE | net wealth <= 500 000 AED |
| credit_good_standing | APPROVE | score >= 550 and 0 active defaults |
| stable_work | APPROVE | >= 12 of last 24 months employed |
| not_in_work | APPROVE | unemployed / student / retired |
| income_above_band | SOFT_DECLINE | income per member > 2500 AED |
| high_net_wealth | SOFT_DECLINE | net wealth > 500 000 AED |
| borderline_income | REVIEW | 2000 <= income per member <= 2500 |
| active_credit_defaults | REVIEW | >= 1 active default |
| poor_credit_score | REVIEW | score < 550 |
| unstable_work_history | REVIEW | employed but < 12 of last 24 months |
| any failed cross-check | REVIEW | |
| any unreadable document | REVIEW | |

## 3. Measured results

Benchmark: `uv run python scripts/benchmark.py data/synthetic/<run-id>` (real extraction, OCR and
rules; fake LLM; in-memory DB). On 100 synthetic packs (seed 7, 30% planted income mismatches):

| Measure | Result |
|---|---|
| Outcome agreement with answer key | 100/100 |
| Extracted eligibility values correct | 600/600 |
| Planted income mismatches caught | 30/30, 0 false alarms on 70 clean packs |
| Decided without a caseworker | 51% (19 approve, 32 soft decline); 49 to review |
| Processing time per case (in-process) | mean 2.9 s, p95 3.5 s, max 5.0 s |
| Through the browser | 7-13 s per decision |
| LLM plan (`qwen2.5:7b`, CPU) | 18-20 s warm, ~40 s cold, up to ~60 s |

Caveat: these are synthetic documents with known layouts. Real scans and other bank formats will
score lower; a pilot on real documents is the honest next measurement.

Run the same benchmark against the team version to compare like for like.

## 4. Lessons worth carrying over

Design:
- **Keep the decision deterministic and explainable.** Rules (later an ML model) decide; the LLM
  only advises on enablement. Every outcome lists all reasons with value, threshold and source.
- **Route uncertainty to a human, never guess.** Unreadable document, low OCR confidence,
  failed cross-check, borderline values: all go to review with the reason written down.
- **The assessor never sees identity.** It receives household facts plus prebuilt findings only.
- **Never send identity to the LLM.** The profile has no name, Emirates ID, employer or exact
  income (income band only). Test the exact request payload to prove it.
- **The LLM must fail safe.** Timeout, bad JSON or empty lists raise; the service substitutes a
  labelled fallback plan. Store the plan with model name, latency and error type.
- **Append-only storage.** Decisions and inputs are never updated or deleted; keep the policy
  version id on every decision.
- **Never log names, Emirates IDs or incomes** (whitelist log keys).

Technical gotchas (each cost time in V1):
- **RapidOCR drops spaces in names** at the card's native size. Upscale images under 2000 px wide
  by 2x before OCR, and compare names ignoring whitespace and case.
- **OCR values must be validated against patterns.** When a field is missing, the next line of the
  card otherwise gets read as its value.
- **Set an OCR confidence threshold** (V1 uses 0.80); below it, treat the card as unreadable.
- **Check uploads by magic bytes**, not file extension; cap size (V1: 10 MB).
- **Multipart forms:** a Pydantic model with `extra="forbid"` rejects the file fields; drop the
  file field names before validating the form.
- **Windows:** always write files with `encoding="utf-8"` (cp1252 corrupts en dashes);
  `uvicorn --reload` can hang and keep serving old routes.
- **Memory (15 GB, CPU only):** `qwen2.5:7b` holds about 5 GB while loaded. Don't keep it loaded
  needlessly (`ollama stop qwen2.5:7b`); `qwen2.5:3b` is the lighter fallback. Run servers in your
  own terminals for demos.
- **Excel files are not byte-reproducible** (zip timestamps); compare cell values in tests.

Process:
- Spec Kit flow per feature (specify, plan, tasks, analyze, implement); `/speckit-analyze` caught
  two critical gaps before any code was written.
- Synthetic packs with answer keys (`social-support-data generate`) make accuracy measurable;
  three fixed demo packs (`social-support-data demo`) make the demo story repeatable.

## 5. What V1 does not have yet (from the brief)

- Agentic orchestration (LangGraph or similar: orchestrator, extraction, validation, eligibility,
  decision agents) and a reasoning framework (ReAct, Reflexion, Plan-and-Solve).
- Interactive chatbot.
- Scikit-learn eligibility classifier (the labelled synthetic packs are ready to train on).
- Langfuse/LangSmith observability.
- ChromaDB / LlamaIndex, PostgreSQL (SQLite via SQLAlchemy, so this is a config swap).
- Address and family-member cross-checks.

## 6. Suggested first session in the revamp folder

1. Run `/init` to create a CLAUDE.md for the team codebase.
2. Ask Claude to read this note and assess the team version against it: what is better, what is
   worse, which V1 modules to port (extraction, cross-checks, rules, anonymised enablement,
   benchmark, demo packs) and which to rewrite.
3. Run the V1 benchmark against the team version if their API can accept the same packs.
4. Decide improve-in-place vs port, then continue with the chatbot and agentic features as new
   Spec Kit features.
