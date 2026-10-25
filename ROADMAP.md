# Roadmap

The prototype is built in thin vertical slices. Each feature gets its own branch and design
folder under [`specs/`](specs/), created with `/speckit-specify` and taken through the Spec Kit
flow (see [README](README.md#how-this-project-is-built)). Feature numbers for planned work are
provisional until the feature is specified.

| # | Feature | Status | Design record |
|---|---|---|---|
| 001 | Application walking skeleton | Done | [`specs/001-application-walking-skeleton/`](specs/001-application-walking-skeleton/) |
| 002 | Synthetic data generator | In progress | [`specs/002-synthetic-data-generator/`](specs/002-synthetic-data-generator/) |
| 003 | Document extraction | Planned | — |
| 004 | Cross-document validation | Planned | — |
| 005 | Eligibility ML classifier | Planned | — |
| 006 | Agent orchestration | Planned | — |
| 007 | Chat and economic enablement | Planned | — |
| 008 | End-to-end observability | Planned | — |

## Scope notes

### 001 Application walking skeleton

An application form produces a stored, explained decision. Applicants look it up by reference
number plus Emirates ID. Borderline cases go to a passcode-protected caseworker review queue. The
assessment is a placeholder income-per-member rule behind the `Assessor` interface. Records are
append-only in SQLite.

### 002 Synthetic data generator

Reproducible, seeded batches of fictional applicant packs: form data plus the five supporting
documents (bank statement, Emirates ID image, resume, assets/liabilities Excel, credit report).
Each pack has an answer key with true values and a labelled expected outcome from an ordered list
of named rules. Inconsistencies (income mismatch, address mismatch, and so on) can be injected on
purpose so later features have something to detect.

### 003 Document extraction

Turn uploaded attachments into structured fields: OCR with RapidOCR (pip-only, CPU) for the Emirates ID
image, parsing for PDFs and the Excel file, and a local LLM (`qwen2.5`) for less structured text
such as resumes. Store raw documents and extracted fields together (multimodal storage), and
measure accuracy against the 002 answer keys. Failed extraction routes to human review.

### 004 Cross-document validation

Reconcile the form against the extracted documents: address (form vs. credit report), income
across bank statement and form, family member details, and identity fields. Produce a list of
named conflicts with severity. Unresolved conflicts send the case to human review instead of
an automated decision.

### 005 Eligibility ML classifier

A scikit-learn classifier trained on 002 data, using income, employment history, family size,
wealth and demographic profile. The algorithm choice is justified by the data's characteristics,
and each prediction comes with its main factors and a confidence score. It plugs in as a new
`Assessor` selected by the `ASSESSOR` setting. Low confidence falls back to human review, and
fairness checks cover the demographic features.

### 006 Agent orchestration

A LangGraph (or similar) workflow with a master orchestrator and extraction, validation,
eligibility and decision-recommendation agents, using a named reasoning pattern (e.g. ReAct or
Reflexion). It runs on local Ollama models, produces an approve or soft-decline recommendation
with an explanation, and is exposed as another `Assessor`.

### 007 Chat and economic enablement

An interactive chat in the Streamlit UI where applicants ask about their application and decision
in plain language. Recommendations for economic enablement (upskilling and training, job
matching, career counselling) are drawn from the applicant's profile, with retrieval over a
ChromaDB knowledge base using `nomic-embed-text` embeddings.

### 008 End-to-end observability

Langfuse (or LangSmith) tracing across the API, agents, LLM calls and the classifier, so any
decision can be followed from submission to recommendation. Builds on the existing trace recorder
and keeps the rule that no personal data (Emirates IDs, names, incomes) is logged.
