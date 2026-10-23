# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

No source code exists yet. The repository currently holds only the brief, `AI Case Study_DGE 5 - Copy.docx`, which defines the take-home assessment this project implements. Update this file with real build/run/test commands and architecture notes once code is added.

## Spec-driven workflow (Spec Kit)

This project is built with GitHub Spec Kit (`specify` CLI 1.2.0, PowerShell scripts). The commands are installed as skills in `.claude/skills/`. The user is learning Spec Kit, so follow the flow rather than writing code ad hoc:

`/speckit-constitution` → per feature: `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-checklist` (optional) → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`

- Project principles live in `.specify/memory/constitution.md`. Every plan must pass its gates.
- Each feature gets a branch and a folder `specs/NNN-feature-name/` (`spec.md`, `plan.md`, `data-model.md`, `contracts/`, `tasks.md`).
- `spec.md` covers *what/why* only. Technology choices belong in `plan.md`.
- Build in thin vertical slices: 001 is a walking skeleton, then synthetic data, extraction, validation, eligibility ML, agent orchestration, chat/enablement, observability.

## Local environment constraints

- Windows, CPU only (no GPU), 15 GB RAM. No Docker, no local Postgres.
- Ollama models: `qwen2.5:7b` (main), `qwen2.5:3b` (fast fallback), `nomic-embed-text` (embeddings). Prefer OCR (Tesseract/EasyOCR) over vision LLMs for ID images.
- Use SQLite through SQLAlchemy for now so that Postgres is a config swap later. ChromaDB runs embedded.
- Python is managed with `uv`.

## What is being built

A prototype that automates a government social security department's application workflow. The current process takes 5–20 working days; the goal is near-100% automated decisions within minutes, with live interaction through a GenAI chatbot.

The system must:
- Ingest an interactive application form plus attachments: bank statement, Emirates ID (image), resume, assets/liabilities Excel file, and credit report. Synthetic or mock data is acceptable.
- Validate and reconcile inconsistencies across documents (e.g. address on the form vs. the credit report, income across financial documents, family member details).
- Assess eligibility on income level, employment history, family size, wealth, and demographic profile.
- Recommend **approve or soft decline** for financial support.
- Recommend **economic enablement** support: upskilling/training, job matching, career counseling.

## Hard requirements from the brief

- **Locally hosted** ML and LLM models (Ollama, LM Studio, OpenWebUI, or LLMWare). No hosted LLM APIs.
- **Multimodal** processing and storage: text, images, tabular data.
- **Interactive chat** UI in Streamlit or Gradio.
- **Agentic orchestration** (LangGraph, LlamaIndex, Phidata, or CrewAI) with these agents: master orchestrator, data extraction, data validation, eligibility check, decision recommendation.
- At least one **agent reasoning framework**: ReAct, Reflexion, Plan-and-Solve, etc.
- **Scikit-learn classifier** for eligibility. The choice of algorithm must be justified in terms of the data's characteristics.
- **Observability** through Langfuse or LangSmith, end to end.
- **Model serving** with FastAPI, Flask, Ollama, LM Studio, or OpenWebUI.
- Language: Python. Data stack: Pandas, LlamaIndex, ChromaDB (vectors), PostgreSQL (structured records).

## Deliverables

- Source in a private GitHub repo.
- `README.md` with clear step-by-step run instructions.
- Solution summary (≤10 pages) covering: an architecture diagram with data flow, tool choices justified on suitability, scalability, maintainability, performance and security, a modular breakdown of the AI workflow, and future improvements and integration (API design, data pipelines).

Evaluation weighs functionality against sections 2–4 of the brief, code modularity and documentation, solution design, integration quality (APIs and pipelines), demo UI usability, and communication.
