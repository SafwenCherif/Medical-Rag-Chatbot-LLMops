# Medical RAG Chatbot — Full Project Description & Operations Report

**Author:** Safwen Cherif  
**Repository:** https://github.com/SafwenCherif/Medical-Rag-Chatbot-LLMops  
**Stack focus:** Retrieval-Augmented Generation (RAG) · LLMOps · CI/CD · Containers · AWS  
**Document purpose:** Exhaustive technical report describing architecture, every file, every important function, technology choices (what + why), runtime and CI/CD flows, and a complete machine setup guide so another engineer can reproduce the system end-to-end.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement & Goals](#2-problem-statement--goals)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Technology Stack (What & Why)](#4-technology-stack-what--why)
5. [Repository Structure](#5-repository-structure)
6. [End-to-End Data & Request Flow](#6-end-to-end-data--request-flow)
7. [Stage-by-Stage Build Narrative](#7-stage-by-stage-build-narrative)
8. [File-by-File Deep Dive](#8-file-by-file-deep-dive)
9. [Function-by-Function Reference](#9-function-by-function-reference)
10. [Configuration & Secrets](#10-configuration--secrets)
11. [Local Development Guide (Clone → Running Chatbot)](#11-local-development-guide-clone--running-chatbot)
12. [Vector Store Rebuild Guide](#12-vector-store-rebuild-guide)
13. [Docker Guide](#13-docker-guide)
14. [AWS ECR Guide](#14-aws-ecr-guide)
15. [Jenkins CI/CD Guide](#15-jenkins-cicd-guide)
16. [AWS App Runner Deployment (Optional / Account-Dependent)](#16-aws-app-runner-deployment-optional--account-dependent)
17. [Pipeline Reference (`Jenkinsfile`)](#17-pipeline-reference-jenkinsfile)
18. [Operational Runbooks & Troubleshooting](#18-operational-runbooks--troubleshooting)
19. [Security Practices](#19-security-practices)
20. [Limitations, Design Trade-offs & Future Work](#20-limitations-design-trade-offs--future-work)
21. [Glossary](#21-glossary)
22. [Appendix: Useful Commands Cheatsheet](#22-appendix-useful-commands-cheatsheet)

---

## 1. Executive Summary

This project is a **Medical Retrieval-Augmented Generation (RAG) chatbot** with a full **LLMOps packaging and delivery path**.

At runtime, a user asks a medical question in a simple web UI. The application:

1. Optionally corrects obvious medical-term typos in the query.
2. Embeds the query and searches a local **FAISS** vector index built from *The Gale Encyclopedia of Medicine* PDF.
3. Injects the top matching text chunks into a constrained prompt.
4. Calls a hosted LLM (**Groq**, with **OpenRouter** as fallback).
5. Returns a short answer grounded in retrieved encyclopedia context.

Around that application sits an LLMOps delivery chain:

- Python packaging via `setup.py` + `requirements.txt`
- Containerization via `Dockerfile` (CPU-only PyTorch to avoid multi‑GB CUDA downloads)
- Continuous integration via **Jenkins**
- Image vulnerability scanning via **Trivy**
- Image publishing to **Amazon ECR**
- Optional continuous deployment trigger to **AWS App Runner** (requires an AWS account plan that includes App Runner)

The system was developed and validated on **Ubuntu Linux** with **Python 3.12**, Docker, Jenkins in Docker, and AWS account `824756206130` (ECR verified). Local Flask serving on port `5000` and Jenkins pipeline stages through **build → scan → push to ECR** were successfully demonstrated.

---

## 2. Problem Statement & Goals

### 2.1 Problem

General-purpose LLMs can hallucinate medical facts. For encyclopedia-grounded Q&A we want answers that stay close to a known corpus rather than relying only on model weights.

### 2.2 Product goals

- Answer medical questions using retrieved passages from a medical encyclopedia PDF.
- Expose a simple browser chat interface.
- Keep answers short and cautious when context is missing.
- Tolerate common spelling mistakes in medical terms.

### 2.3 Engineering / LLMOps goals

- Modular code: config, logging, exceptions, ingestion, embeddings, retrieval, LLM, UI.
- Reproducible installs and containers.
- CI that builds, scans, and publishes images automatically from GitHub.
- Clear secrets hygiene (`.env` never committed).

### 2.4 Non-goals

- Not a clinical decision-support system and not medical advice.
- Not a multi-tenant SaaS with authentication, billing, or audit trails.
- Not GPU training; embeddings run on CPU with a compact Sentence-Transformers model.

---

## 3. High-Level Architecture

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                           USER BROWSER                                    │
│                     http://localhost:5000                                 │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │ HTTP GET/POST
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     Flask App (app/application.py)                        │
│  - session chat history                                                   │
│  - create_qa_chain() per question                                         │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌──────────────────┐   ┌──────────────────────┐   ┌─────────────────────┐
│ Query correction │   │ FAISS retriever      │   │ Prompt + LLM        │
│ (Groq/OpenRouter)│   │ k=3 chunks           │   │ RetrievalQA stuff   │
└──────────────────┘   └──────────┬───────────┘   └──────────▲──────────┘
                                  │                          │
                                  ▼                          │
                       ┌──────────────────────┐              │
                       │ HuggingFace embeddings│              │
                       │ all-MiniLM-L6-v2      │──────────────┘
                       └──────────┬───────────┘
                                  │
                       ┌──────────▼───────────┐
                       │ vectorstore/db_faiss │
                       │ (index.faiss + .pkl) │
                       └──────────────────────┘

Offline / one-time indexing path:
  data/*.pdf → load → chunk → embed → save FAISS
  (app/components/data_loader.py)

CI/CD path:
  GitHub → Jenkins → docker build → Trivy → AWS ECR → (optional) App Runner
```

### 3.1 Conceptual layers

| Layer | Responsibility |
|---|---|
| Presentation | HTML/CSS Jinja template + Flask routes |
| Orchestration | RetrievalQA chain + query correction wrapper |
| Intelligence | Groq / OpenRouter chat models |
| Retrieval | FAISS similarity search over chunk embeddings |
| Ingestion | PDF load + recursive character splitting |
| Platform | Docker, Jenkins, Trivy, AWS ECR/App Runner |
| Cross-cutting | logging, custom exceptions, dotenv config |

---

## 4. Technology Stack (What & Why)

### 4.1 Application & RAG

| Technology | What it is | Why it was chosen |
|---|---|---|
| **Python 3.12** (local) / **3.10-slim** (Docker) | Runtime | Modern local tooling; Docker uses widely compatible slim base |
| **Flask** | Lightweight web framework | Minimal chat UI with sessions; easy to containerize |
| **Jinja2 templates** | Server-rendered HTML | Simple, no frontend build step |
| **LangChain ecosystem** | RAG glue (loaders, splitters, chains, vector stores) | Fast composition of PDF → chunks → FAISS → RetrievalQA |
| **langchain-community** | Community integrations (PyPDF, FAISS wrappers) | Mature loaders/stores for this pattern |
| **langchain-text-splitters** | `RecursiveCharacterTextSplitter` | LangChain 1.x moved splitters here |
| **langchain-classic** | Classic `RetrievalQA` chain | Still the clearest teaching/production pattern for stuff-chain RAG |
| **langchain-huggingface** | Embedding wrappers | Clean bridge to Sentence-Transformers |
| **sentence-transformers / all-MiniLM-L6-v2** | Compact embedding model (~384 dims) | Good quality/speed/size trade-off on CPU |
| **FAISS (`faiss-cpu`)** | Vector similarity index | Local, fast, no managed DB required for this project size |
| **pypdf** | PDF parsing backend for LangChain loader | Reliable PDF text extraction |
| **python-dotenv** | Load `.env` into process env | Keeps secrets out of source |
| **Groq (`langchain-groq`)** | Hosted LLM inference API | Fast and cost-effective for chat completions |
| **OpenRouter (`langchain-openai` + custom base URL)** | Alternative OpenAI-compatible gateway | Fallback if Groq key unavailable |

### 4.2 Packaging & runtime ops

| Technology | Why |
|---|---|
| **setuptools / setup.py** | Install project as editable package so `from app...` imports work everywhere |
| **venv** | Isolate dependencies from system Python |
| **Docker** | Reproduce runtime across machines and CI |
| **CPU-only PyTorch wheel** | Embeddings need Torch, not NVIDIA CUDA; avoids ~GBs of GPU packages |

### 4.3 CI/CD & cloud

| Technology | Why |
|---|---|
| **GitHub** | Source of truth for Jenkins SCM checkout |
| **Jenkins (LTS in Docker)** | Pipeline automation (clone/build/scan/push/deploy) |
| **Docker socket mount** | Jenkins builds images using host Docker Engine |
| **Trivy** | Container CVE scanning before publish |
| **AWS IAM user + access keys** | Programmatic AWS auth for Jenkins/`aws` CLI |
| **Amazon ECR** | Private Docker registry for the app image |
| **AWS App Runner** | Managed container hosting with public HTTPS URL (account entitlement required) |

### 4.4 Knowledge corpus

| Asset | Why |
|---|---|
| `data/The_GALE_ENCYCLOPEDIA_of_MEDICINE_SECOND.pdf` | Domain corpus for grounded medical Q&A |
| Prebuilt `vectorstore/db_faiss/` | Lets the app answer immediately without re-embedding the full PDF on every machine |

---

## 5. Repository Structure

```text
Medical RAG Chatbot/
├── app/
│   ├── __init__.py
│   ├── application.py                 # Flask entrypoint & routes
│   ├── common/
│   │   ├── __init__.py
│   │   ├── custom_exception.py        # Rich exception formatting
│   │   └── logger.py                  # Daily file logging
│   ├── components/
│   │   ├── __init__.py
│   │   ├── data_loader.py             # Offline PDF → FAISS pipeline
│   │   ├── embeddings.py              # Sentence-Transformers loader
│   │   ├── llm.py                     # Groq / OpenRouter factory
│   │   ├── pdf_loader.py              # PDF load + chunking
│   │   ├── retriever.py               # Prompt + RetrievalQA + typo fix
│   │   └── vector_store.py            # FAISS load/save
│   ├── config/
│   │   ├── __init__.py
│   │   └── config.py                  # Env + RAG constants
│   └── templates/
│       └── index.html                 # Chat UI
├── custom_jenkins/
│   └── Dockerfile                     # Jenkins + Docker CLI image
├── data/
│   └── The_GALE_ENCYCLOPEDIA_of_MEDICINE_SECOND.pdf
├── vectorstore/
│   └── db_faiss/
│       ├── index.faiss
│       └── index.pkl
├── Dockerfile                         # Application image
├── Jenkinsfile                        # CI/CD definition
├── requirements.txt
├── setup.py
├── .env.example                       # Template for secrets
├── .env                               # Local secrets (gitignored)
├── .gitignore
├── .dockerignore
├── full-project-description.md        # This report
└── README-level notes in this file only
```

### 5.1 Intentionally excluded from git

Controlled by `.gitignore`:

- `venv/`, `.venv/`
- `.env`
- `logs/`, `*.log`
- `__pycache__/`, `*.pyc`, `*.egg-info/`
- AWS key CSVs (`*.csv`, `deepuser_accessKeys.csv`)
- `.docker-config/` (local Docker auth helper files)
- local reference folders not part of the runtime app (if present)

---

## 6. End-to-End Data & Request Flow

### 6.1 Offline indexing flow (build the brain)

```text
PDF in data/
   → DirectoryLoader + PyPDFLoader (one Document per page/section)
   → RecursiveCharacterTextSplitter(chunk_size=500, overlap=50)
   → HuggingFaceEmbeddings(all-MiniLM-L6-v2)
   → FAISS.from_documents(...)
   → save_local(vectorstore/db_faiss)
```

**Why chunking?** LLMs and retrievers work better on small coherent passages than whole encyclopedia pages. Overlap preserves continuity across boundaries.

**Why FAISS local files?** No network dependency at query time for retrieval; cheap to ship inside the Docker image.

### 6.2 Online question-answering flow

```text
Browser POST prompt
   → Flask index() stores user message in session
   → create_qa_chain()
        → load_vector_store() + load_llm()
        → CorrectingQAChain.invoke(query)
             → _correct_medical_query(llm, query)
             → FAISS retriever k=3
             → PromptTemplate fills {context}/{question}
             → LLM generation
   → assistant message stored in session
   → redirect GET / renders chat
```

**Why redirect after POST?** Prevents duplicate submissions on browser refresh (PRG pattern: Post/Redirect/Get).

**Why rebuild chain per request?** Simple and safe for a learning/production-light architecture (no shared mutable chain state). The embedding model may be reloaded; this is acceptable for demo scale and can be cached later.

### 6.3 CI/CD flow

```text
Developer git push → GitHub main
   → Jenkins pipeline medical-rag-pipeline
        1) checkout with github-token
        2) aws ecr login with aws-token
           docker build
           trivy image scan (non-blocking)
           docker push to ECR
        3) apprunner start-deployment (if service exists & account allows)
```

---

## 7. Stage-by-Stage Build Narrative

This section documents the work performed to bring the system from empty workspace to working local app + CI publishing.

### Stage 1 — Project setup & configuration

**What we did**

- Scaffolded the `app/` package layout (`common`, `components`, `config`, `templates`).
- Created Python virtualenv with `python3.12 -m venv venv`.
- Added `requirements.txt`, `setup.py`, `.env.example`, `.gitignore`.
- Installed the project editable: `pip install -e .` (after installing CPU Torch first).
- Loaded secrets through dotenv (`GROQ_API_KEY`, optional `OPENROUTER_API_KEY`).

**Why**

- Virtualenv prevents dependency conflicts with system packages.
- Editable install makes `import app...` reliable from any working directory.
- Central config avoids hard-coded secrets and magic numbers.

### Stage 2 — Data processing & storage

**What we did**

- Placed the Gale Encyclopedia PDF under `data/`.
- Implemented PDF loading and chunking.
- Implemented embeddings + FAISS save/load.
- Used/verified a prebuilt FAISS index in `vectorstore/db_faiss/` so local Q&A works without a multi-hour full re-embed on first run.

**Why**

- Separation of ingestion (`data_loader.py`) from serving means the chat app does not re-parse the PDF on every question.
- Prebuilt index greatly improves onboarding speed for clones.

### Stage 3 — LLM & retrieval

**What we did**

- Implemented `load_llm()` with Groq primary and OpenRouter fallback.
- Implemented RetrievalQA prompt constraining answers to context.
- Improved retrieval robustness:
  - retrieve `k=3` chunks (instead of 1),
  - add medical typo correction before retrieval.

**Why**

- Grounding reduces hallucinations relative to pure LLM answers.
- `k=1` was brittle: one poor neighbor caused empty/useless answers.
- Typo correction fixed cases like `algesic` → `analgesic`, `epathit` → `hepatitis`.

### Stage 4 — Application layer

**What we did**

- Built Flask routes `/` and `/clear`.
- Built HTML chat UI with user/assistant bubbles and error rendering.
- Ran app on `0.0.0.0:5000` and validated chat via browser and HTTP clients.

**Why**

- Flask keeps the UI simple while proving the RAG chain in a real request path.
- Binding `0.0.0.0` makes Docker/App Runner networking work (not only localhost).

### Stage 5 — Versioning, containers, CI/CD, cloud registry

**What we did**

- Initialized git, committed project, pushed to GitHub.
- Authored/updated `Dockerfile` with CPU Torch strategy and `.dockerignore`.
- Built and pushed image to ECR repository `medical-rag-chatbot`.
- Built custom Jenkins image with Docker CLI.
- Ran Jenkins on host port `8080`, configured credentials (`github-token`, `aws-token`).
- Installed AWS CLI + Trivy inside Jenkins.
- Created Jenkins pipeline job reading `Jenkinsfile` from SCM.
- Observed successful clone/build/scan/push; App Runner stage blocked by AWS Free Plan / subscription entitlement.

**Why each piece**

- GitHub: single source for code promotion.
- Docker: identical runtime in CI and cloud.
- Trivy: security gate visibility for HIGH/CRITICAL CVEs.
- ECR: durable private artifact storage.
- Jenkins: explicit, inspectable pipeline stages for LLMOps learning/ops.
- App Runner: managed HTTPS deploy without running your own VM (when account allows).

---

## 8. File-by-File Deep Dive

### 8.1 Root packaging & ops files

#### `setup.py`

**What:** setuptools package metadata and dependency wiring.  
**Why:** `pip install -e .` installs requirements and exposes the `app` package.

Key behavior:

- Reads `requirements.txt` line-by-line into `install_requires`.
- `find_packages()` discovers `app` and subpackages.
- Version `0.1`, author set to project owner.

#### `requirements.txt`

**What:** Direct Python dependencies.  
**Why:** Declares the library surface area without pinning every transitive package (flexible across 2026 package churn). Includes LangChain packages, FAISS, pypdf, Flask, dotenv, sentence-transformers, Groq + OpenAI clients.

#### `.env.example`

**What:** Committed template of required environment variables.  
**Why:** Documents secrets without exposing real keys. Cloners copy it to `.env`.

#### `.env` (local only)

**What:** Real keys (`GROQ_API_KEY`, optional OpenRouter/AWS values).  
**Why:** Runtime configuration. Must never be committed.

#### `.gitignore`

**What:** Git exclusion rules.  
**Why:** Prevents secrets, virtualenvs, logs, caches, and local Docker config from leaking into GitHub.

#### `.dockerignore`

**What:** Build-context exclusions for `docker build`.  
**Why:** Keeps secrets and huge irrelevant folders out of the image build context; faster/safer builds.

#### `Dockerfile`

**What:** Application container definition.  
**Why / design choices:**

- Base `python:3.10-slim` for small footprint.
- `PYTHONDONTWRITEBYTECODE` and `PYTHONUNBUFFERED` for cleaner containers/logs.
- Install `build-essential` + `curl` for compiling/native deps when needed.
- Install **CPU Torch first**, then project deps with the CPU index — critical for disk/time.
- `COPY . .` includes `app/`, `data/`, and `vectorstore/` so the container can answer without re-indexing.
- `EXPOSE 5000` and `CMD python app/application.py`.

#### `Jenkinsfile`

**What:** Declarative Jenkins pipeline.  
**Why:** Codifies CI/CD so builds are reproducible and reviewable in git.

Environment variables:

- `AWS_REGION=us-east-1`
- `ECR_REPO=medical-rag-chatbot`
- `IMAGE_TAG=latest`
- `SERVICE_NAME=llmops-medical-service`

Stages detailed in [Section 17](#17-pipeline-reference-jenkinsfile).

#### `custom_jenkins/Dockerfile`

**What:** Jenkins LTS image plus Docker CLI binary.  
**Why:** Pipeline needs `docker` commands. Rather than running a full Docker daemon inside Jenkins, we mount the host `/var/run/docker.sock` and only install the CLI. This is simpler and more reliable on modern Debian-based Jenkins LTS images.

#### `full-project-description.md`

**What:** This report.  
**Why:** Single onboarding + architecture source of truth for humans.

---

### 8.2 `app/application.py` — Flask application

**What:** Web server entrypoint.  
**Why:** Connects human interaction to the RAG chain.

Responsibilities:

1. Load dotenv.
2. Create Flask app + random `secret_key` for signed sessions.
3. Register Jinja filter `nl2br` so newlines render as `<br>` safely via Markup.
4. Route `/`:
   - Initialize `session["messages"]`.
   - On POST: append user message, invoke QA chain, append assistant message, redirect.
   - On GET: render template with history.
5. Route `/clear`: wipe session messages.
6. `__main__`: run on `0.0.0.0:5000`, `debug=False`, `use_reloader=False` (important in containers to avoid double-process startup).

---

### 8.3 `app/config/config.py` — configuration hub

**What:** Central constants and env reads.  
**Why:** One place to change chunking, paths, and model-related env wiring.

Exports:

| Symbol | Meaning |
|---|---|
| `HF_TOKEN` | Optional Hugging Face token |
| `GROQ_API_KEY` | Primary LLM key |
| `OPENROUTER_API_KEY` | Fallback LLM key |
| `OPENROUTER_MODEL` | Fallback model id |
| `HUGGINGFACE_REPO_ID` | Reserved/legacy experiment constant |
| `DB_FAISS_PATH` | `vectorstore/db_faiss` |
| `DATA_PATH` | `data/` |
| `CHUNK_SIZE` | `500` characters |
| `CHUNK_OVERLAP` | `50` characters |

Calls `load_dotenv()` at import so any module importing config sees `.env` values.

---

### 8.4 `app/common/logger.py`

**What:** Project logging factory.  
**Why:** Persistent, timestamped diagnostics for ingestion and request-time failures.

Mechanics:

- Ensures `logs/` exists.
- Writes to `logs/log_YYYY-MM-DD.log`.
- `get_logger(name)` returns a named logger at INFO.

Usage pattern across components:

```python
logger = get_logger(__name__)
logger.info("...")
logger.error("...")
```

---

### 8.5 `app/common/custom_exception.py`

**What:** Exception subclass that embeds file/line context.  
**Why:** Faster debugging than bare `Exception("failed")` when RAG pipelines fail deep in nested calls.

Mechanics:

- Captures `sys.exc_info()` traceback frame.
- Formats: `message | Error: <detail> | File: <path> | Line: <n>`.

---

### 8.6 `app/components/pdf_loader.py`

**What:** PDF ingestion utilities.  
**Why:** Convert encyclopedia PDF into LangChain `Document` objects and then into overlapping chunks.

Functions:

- `load_pdf_files()` — DirectoryLoader over `DATA_PATH` with `*.pdf` + `PyPDFLoader`.
- `create_text_chunks(documents)` — `RecursiveCharacterTextSplitter`.

Failure handling: log + return empty list rather than crash the whole process in loader utilities (callers decide how to treat emptiness).

---

### 8.7 `app/components/embeddings.py`

**What:** Embedding model factory.  
**Why:** Same embedding model must be used for indexing and querying; mismatches destroy retrieval quality.

Function:

- `get_embedding_model()` → `HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")`.

First call may download model weights from Hugging Face Hub (network required once; then cached locally).

---

### 8.8 `app/components/vector_store.py`

**What:** FAISS persistence API.  
**Why:** Save expensive embeddings to disk; load quickly at serving time.

Functions:

- `load_vector_store()` — if path exists, `FAISS.load_local(..., allow_dangerous_deserialization=True)`.
- `save_vector_store(text_chunks)` — `FAISS.from_documents` + `save_local`.

Note on `allow_dangerous_deserialization=True`:

- FAISS LangChain loader may unpickle metadata.
- Safe when you trust the index files you yourself generated/committed.
- Do not load untrusted pickle indexes from unknown sources.

---

### 8.9 `app/components/data_loader.py`

**What:** Orchestrates offline indexing.  
**Why:** Single command to regenerate FAISS from PDFs after corpus changes.

Function:

- `process_and_store_pdfs()` chains load → chunk → save.

Runnable as:

```bash
python -m app.components.data_loader
```

---

### 8.10 `app/components/llm.py`

**What:** LLM client factory.  
**Why:** Isolate provider choice; keep app code provider-agnostic.

Function `load_llm(model_name="llama-3.1-8b-instant", ...)`:

1. If `GROQ_API_KEY` present → `ChatGroq` with temperature `0.3`, `max_tokens=256`.
2. Else if `OPENROUTER_API_KEY` → `ChatOpenAI` pointed at `https://openrouter.ai/api/v1`.
3. Else raise/log custom exception and return `None`.

**Why low max_tokens?** Encourages concise medical blurbs aligned with the UI prompt and reduces cost/latency.

---

### 8.11 `app/components/retriever.py`

**What:** The RAG brain for online answering.  
**Why:** Connect retrieval + prompting + generation and harden against typos.

Pieces:

1. `CUSTOM_PROMPT_TEMPLATE` — instructions: answer from context only; map typos; refuse when unsupported.
2. `set_custom_prompt()` — LangChain `PromptTemplate`.
3. `_correct_medical_query(llm, query)` — cheap rewrite call.
4. `create_qa_chain()` — builds `RetrievalQA` (`chain_type="stuff"`, `k=3`) and wraps it in `CorrectingQAChain`.

`stuff` chain type meaning:

- Retrieved documents are concatenated (“stuffed”) into one prompt.
- Best for small `k` and short chunks (our case).

---

### 8.12 `app/templates/index.html`

**What:** Chat UI.  
**Why:** Minimal usable frontend without Node toolchain.

Behavior:

- Loops `messages` into styled bubbles (`user` vs `assistant`).
- Shows `error` if present.
- POST form field `prompt`.
- Separate GET form to `/clear`.

Uses filter `| nl2br` for multiline answers.

---

### 8.13 Data & vectorstore artifacts

#### `data/The_GALE_ENCYCLOPEDIA_of_MEDICINE_SECOND.pdf`

Source corpus. Without this (or another PDF in `data/`), indexing cannot run.

#### `vectorstore/db_faiss/index.faiss` + `index.pkl`

FAISS numeric index + LangChain docstore/metadata pickle. Required for serving if you do not rebuild.

---

### 8.14 `__init__.py` files

Empty package markers under `app/`, `app/common/`, `app/components/`, `app/config/`.  
**Why:** Make directories importable Python packages for setuptools and runtime imports.

---

## 9. Function-by-Function Reference

### 9.1 Logging & errors

#### `get_logger(name: str)`

- **Input:** module name (usually `__name__`).
- **Output:** `logging.Logger`.
- **Why:** Consistent log attribution per module.

#### `CustomException.__init__(message, error_detail=None)`

- Builds detailed message and passes to `Exception`.
- **Why:** Preserve root cause + location.

#### `CustomException.get_detailed_error_message(message, error_detail)`

- Static formatter using traceback frame.
- **Why:** One standard error string shape.

---

### 9.2 Config symbols

Not functions, but critical “API” of the app:

- Paths: `DATA_PATH`, `DB_FAISS_PATH`
- Chunking: `CHUNK_SIZE`, `CHUNK_OVERLAP`
- Secrets: `GROQ_API_KEY`, `OPENROUTER_*`, `HF_TOKEN`

---

### 9.3 Ingestion

#### `load_pdf_files()`

- Validates `DATA_PATH`.
- Loads all `*.pdf`.
- Returns `List[Document]` or `[]` on failure.

#### `create_text_chunks(documents)`

- Splits docs with recursive separators (paragraphs → sentences → words).
- Returns chunk list or `[]`.

#### `process_and_store_pdfs()`

- Full offline pipeline.
- Side effect: writes FAISS directory.

---

### 9.4 Embeddings & FAISS

#### `get_embedding_model()`

- Returns embedding model instance.
- Raises `CustomException` on failure (unlike some loaders that soft-fail).

#### `save_vector_store(text_chunks)`

- Builds FAISS from chunks using embedding model.
- Saves under `DB_FAISS_PATH`.

#### `load_vector_store()`

- Returns FAISS instance or warns if missing.

---

### 9.5 LLM & retrieval

#### `load_llm(...)`

- Provider selection + client construction.
- Returns LLM object or `None`.

#### `set_custom_prompt()`

- Returns PromptTemplate with `context` and `question` variables.
- Note: RetrievalQA maps the user query into the prompt variable expected by the chain.

#### `_correct_medical_query(llm, query)`

- Asks LLM to return only corrected question.
- Falls back to original query on any error.

#### `create_qa_chain()`

- Validates vector store + LLM.
- Builds RetrievalQA with `k=3`.
- Returns wrapper exposing `.invoke({"query": ...})` like a chain.

#### `CorrectingQAChain.invoke(inputs)`

- Extracts query.
- Corrects typos.
- Delegates to RetrievalQA.

---

### 9.6 Flask handlers

#### `nl2br(value)`

- Jinja filter converting `\n` to `<br>\n` with Markup.
- **Why:** Render multi-line model outputs without enabling arbitrary HTML from model (content is still passed through `| safe` in template — see security notes).

#### `index()`

- Main chat endpoint.

#### `clear()`

- Session reset endpoint.

---

## 10. Configuration & Secrets

### 10.1 Required for local chat

```bash
GROQ_API_KEY=gsk_...
```

Get a key from https://console.groq.com/keys

### 10.2 Optional fallback

```bash
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct
```

### 10.3 Optional Hugging Face

```bash
HF_TOKEN=hf_...
```

Helps with authenticated model downloads / higher rate limits. Not strictly required for public models.

### 10.4 AWS (CI/CD)

Used by host/`aws` CLI and Jenkins credential `aws-token`:

- Access Key ID
- Secret Access Key
- Region `us-east-1`
- IAM permissions ideally include:
  - `AmazonEC2ContainerRegistryFullAccess` (or tighter custom policy)
  - `AWSAppRunnerFullAccess` (only useful if App Runner is entitled on the account)

### 10.5 GitHub (CI/CD)

Classic Personal Access Token scopes typically:

- `repo`
- `admin:repo_hook` (useful for webhook integrations)

Stored in Jenkins as credential ID **`github-token`** (username = GitHub username, password = token).

---

## 11. Local Development Guide (Clone → Running Chatbot)

These steps assume **Ubuntu/Debian-like Linux**. macOS is similar; Windows users should use WSL2 Ubuntu for closest results.

### 11.1 Prerequisites

```bash
# system packages
sudo apt update
sudo apt install -y python3.12 python3.12-venv git curl

# Docker Engine + permissions
sudo apt install -y docker.io
sudo usermod -aG docker "$USER"
# log out/in after group change
docker --version
```

Optional for full CI/CD later:

- AWS account + IAM access keys
- Jenkins via Docker (section 15)
- `aws` CLI v2

### 11.2 Clone

```bash
git clone https://github.com/SafwenCherif/Medical-Rag-Chatbot-LLMops.git
cd Medical-Rag-Chatbot-LLMops
```

Confirm important paths exist:

```bash
ls app data vectorstore/db_faiss Dockerfile Jenkinsfile requirements.txt setup.py
```

### 11.3 Create virtual environment

```bash
python3.12 -m venv venv
source venv/bin/activate
python --version   # expect 3.12.x
pip install --upgrade pip
```

### 11.4 Install dependencies (CPU Torch first)

This avoids pip resolving huge CUDA wheels:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install --extra-index-url https://download.pytorch.org/whl/cpu -e .
```

Verify imports:

```bash
python - <<'PY'
import flask, faiss, langchain, langchain_groq, sentence_transformers
print("imports OK")
PY
```

### 11.5 Configure secrets

```bash
cp .env.example .env
nano .env   # or use any editor
```

Minimum:

```env
GROQ_API_KEY=your_key_here
```

### 11.6 (Optional) Smoke-test retrieval + LLM

```bash
python - <<'PY'
from app.components.vector_store import load_vector_store
from app.components.retriever import create_qa_chain

db = load_vector_store()
print("FAISS:", type(db).__name__)
print(db.similarity_search("What is diabetes?", k=1)[0].page_content[:200])

qa = create_qa_chain()
print(qa.invoke({"query": "What is hepatitis?"})["result"])
PY
```

First embedding-model load downloads weights; need network.

### 11.7 Run the web app

```bash
source venv/bin/activate
python app/application.py
```

Open: http://localhost:5000

Try:

- `What is diabetes?`
- `what is the role of algesic` (typo tolerance demo)
- `what is epathit` (should map toward hepatitis)

Clear chat with the **Clear Chat** button.

### 11.8 Stop the server

`Ctrl+C` in the terminal running Flask.

---

## 12. Vector Store Rebuild Guide

Rebuild if you change the PDF corpus, chunk size, or embedding model.

```bash
source venv/bin/activate
# optional: remove old index
rm -rf vectorstore/db_faiss

python -m app.components.data_loader
ls -lh vectorstore/db_faiss
```

**Why this can take time:** embedding thousands of chunks on CPU is compute-heavy. Prefer keeping a generated index in the repo/image for normal setup.

If you change `CHUNK_SIZE`, `CHUNK_OVERLAP`, or embedding model name, old indexes become incompatible or suboptimal — rebuild.

---

## 13. Docker Guide

### 13.1 Build application image

From repo root:

```bash
docker build -t medical-rag-chatbot:latest .
```

**Why `.dockerignore` matters:** prevents `.env` and `venv/` from entering build context.

### 13.2 Run container locally

```bash
docker run --rm -p 5000:5000 \
  -e GROQ_API_KEY="$(grep ^GROQ_API_KEY= .env | cut -d= -f2-)" \
  medical-rag-chatbot:latest
```

Then open http://localhost:5000

### 13.3 Image design notes for operators

- Image includes FAISS index → larger image, faster cold start answering.
- CPU Torch keeps image smaller than CUDA stacks (still multi‑GB because of Torch + Transformers).
- Runtime secret injection via `-e` / orchestrator env vars; do not bake keys into layers.

---

## 14. AWS ECR Guide

### 14.1 Create repository

Console (region **us-east-1**):

1. ECR → Repositories → Create  
2. Visibility: **Private**  
3. Name: **`medical-rag-chatbot`**  
4. Tag mutability: Mutable  
5. Encryption: AES-256  
6. Create

Expected URI shape:

```text
<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/medical-rag-chatbot
```

CLI alternative:

```bash
aws ecr create-repository --repository-name medical-rag-chatbot --region us-east-1
```

### 14.2 Authenticate Docker to ECR

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
```

If `~/.docker` is root-owned and login fails, use a project-local Docker config:

```bash
export DOCKER_CONFIG="$PWD/.docker-config"
mkdir -p "$DOCKER_CONFIG"
```

(Then re-run login/push with that env var set.)

### 14.3 Tag and push

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI=${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/medical-rag-chatbot
docker tag medical-rag-chatbot:latest ${ECR_URI}:latest
docker push ${ECR_URI}:latest
aws ecr describe-images --repository-name medical-rag-chatbot --region us-east-1
```

---

## 15. Jenkins CI/CD Guide

### 15.1 Why Jenkins in this project

Jenkins provides visible stages for:

1. Pulling source from GitHub  
2. Building Docker images  
3. Scanning with Trivy  
4. Publishing to ECR  
5. Triggering a cloud redeploy  

This makes the LLMOps lifecycle inspectable for learning and for team operations.

### 15.2 Build custom Jenkins image

```bash
cd custom_jenkins
docker build -t jenkins-dind .
cd ..
```

### 15.3 Run Jenkins (host Docker socket)

```bash
docker rm -f jenkins-dind 2>/dev/null || true

docker run -d \
  --name jenkins-dind \
  --group-add "$(getent group docker | cut -d: -f3)" \
  -p 8080:8080 \
  -p 50000:50000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v jenkins_home:/var/jenkins_home \
  jenkins-dind
```

Get initial admin password:

```bash
docker exec jenkins-dind cat /var/jenkins_home/secrets/initialAdminPassword
```

Open http://localhost:8080 → unlock → install suggested plugins → create admin user.

### 15.4 Install tools inside Jenkins container

```bash
docker exec -u root jenkins-dind bash -lc '
apt-get update -y
apt-get install -y --no-install-recommends curl unzip ca-certificates python3 python3-pip
ln -sf /usr/bin/python3 /usr/bin/python

# AWS CLI v2
cd /tmp
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -qo awscliv2.zip
./aws/install

# Trivy
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
  | sh -s -- -b /usr/local/bin

aws --version
trivy --version
docker version --format "{{.Client.Version}}"
chmod 666 /var/run/docker.sock || true
'

docker restart jenkins-dind
```

### 15.5 Install Jenkins plugins for AWS credentials

Manage Jenkins → Plugins → Available:

- **AWS Credentials**
- Related AWS SDK / Pipeline AWS plugins as suggested by dependency resolver

Restart Jenkins if prompted.

### 15.6 Add credentials

Manage Jenkins → Credentials → System → Global credentials → Add:

#### GitHub credential

| Field | Value |
|---|---|
| Kind | Username with password |
| Username | your GitHub username |
| Password | GitHub PAT (`ghp_...`) |
| ID | `github-token` |
| Description | GitHub access for Jenkins |

#### AWS credential

| Field | Value |
|---|---|
| Kind | AWS Credentials |
| Access Key ID | `AKIA...` |
| Secret Access Key | secret |
| ID | `aws-token` |
| Description | AWS ECR for Jenkins |

IDs must match `Jenkinsfile` exactly.

### 15.7 Create pipeline job

1. New Item → name `medical-rag-pipeline` → Pipeline → OK  
2. Pipeline definition: **Pipeline script from SCM**  
3. SCM: Git  
4. Repository URL: `https://github.com/SafwenCherif/Medical-Rag-Chatbot-LLMops.git`  
5. Credentials: `github-token`  
6. Branch: `*/main`  
7. Script Path: `Jenkinsfile`  
8. Save  

### 15.8 Run build

Click **Build Now**, then open **Console Output**.

Expected healthy progression:

1. Clone succeeds  
2. Docker build succeeds  
3. Trivy runs (may warn; currently non-blocking via `|| true`)  
4. Push to ECR succeeds  
5. App Runner stage succeeds **only if** service exists and account entitles App Runner API

### 15.9 Monitoring logs from terminal

Without using browser DevTools, operators can read Jenkins logs from the container filesystem:

```bash
docker exec jenkins-dind bash -lc '
L=$(ls -1d /var/jenkins_home/jobs/medical-rag-pipeline/builds/[0-9]* | sort -n | tail -1)
echo "Build dir: $L"
tail -n 80 "$L/log"
grep -E "Finished:|ERROR|digest:" "$L/log" | tail -20
'
```

---

## 16. AWS App Runner Deployment (Optional / Account-Dependent)

### 16.1 Intent

App Runner turns the ECR image into a publicly reachable HTTPS service without managing EC2/Kubernetes.

Service naming expected by `Jenkinsfile`:

- Service name: `llmops-medical-service`
- Region: `us-east-1`
- Port: `5000`
- Env: `GROQ_API_KEY`

### 16.2 Console steps (when account allows)

1. Open App Runner in **us-east-1**  
2. Create service  
3. Source: Container registry → Amazon ECR → `medical-rag-chatbot:latest`  
4. Let AWS create ECR access role  
5. Configure:
   - Name `llmops-medical-service`
   - Port `5000`
   - Env var `GROQ_API_KEY`
   - Smallest CPU/memory for cost control
6. Create & deploy  
7. Copy default domain URL and test chat  

### 16.3 Known blocker observed in this project environment

AWS Free Plan / incomplete paid-tier activation can return:

```text
SubscriptionRequiredException:
The AWS Access Key Id needs a subscription for the service
```

Console may show **Complete your account setup** and refuse App Runner. Completing registration/upgrade often requires root-account billing activation; if unavailable, stop at ECR + Jenkins (still a complete CI artifact pipeline) and host elsewhere later (EC2, Lightsail, another cloud, or keep local Docker).

### 16.4 After App Runner exists

Re-run Jenkins **Build Now**. Deploy stage should call:

```bash
aws apprunner start-deployment --service-arn <arn> --region us-east-1
```

---

## 17. Pipeline Reference (`Jenkinsfile`)

### 17.1 Stage: Clone GitHub Repo

- Uses `checkout scmGit` with credential `github-token`
- Branch: `main`
- **Why:** Ensures Jenkins builds the committed project, not a stale workspace copy only.

### 17.2 Stage: Build, Scan, and Push Docker Image to ECR

Inside `withCredentials(aws-token)`:

1. Resolve account ID via STS  
2. Compose ECR URL  
3. `docker login` to ECR  
4. `docker build -t medical-rag-chatbot:latest .`  
5. `trivy image ... -o trivy-report.json || true`  
6. `docker tag` + `docker push`  
7. Archive Trivy report as Jenkins artifact  

**Why Trivy is non-blocking (`|| true`):** first delivery prioritizes green publish while still producing a scan artifact for human review. For stricter prod gates, remove `|| true` and/or use `--exit-code 1`.

### 17.3 Stage: Deploy to AWS App Runner

- Looks up service ARN by name `llmops-medical-service`
- Fails clearly if missing
- Triggers `start-deployment`

**Why separate stage?** Separates artifact publishing from release orchestration; artifacts can still be useful if deploy targets are unavailable.

---

## 18. Operational Runbooks & Troubleshooting

### 18.1 Flask starts but chat errors “QA chain could not be created”

Checks:

```bash
test -f vectorstore/db_faiss/index.faiss && echo index_ok
grep GROQ_API_KEY .env
python -c "from app.components.llm import load_llm; print(load_llm())"
```

### 18.2 Embedding download failures / HF rate limits

- Ensure network access.
- Optionally set `HF_TOKEN` in `.env`.
- Retry; models cache under `~/.cache/huggingface`.

### 18.3 Answers say context missing for misspelled terms

- Confirm you are on latest `retriever.py` with typo correction + `k=3`.
- Restart Flask (Python modules are imported at process start).

### 18.4 Docker build downloads CUDA packages

- Ensure Dockerfile installs CPU Torch first (current Dockerfile does).
- Locally prefer:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 18.5 `docker login` ECR permission denied on config.json

- `~/.docker` may be root-owned.
- Use `DOCKER_CONFIG` pointing to a writable directory (section 14.2).

### 18.6 Jenkins cannot run docker

```bash
docker exec jenkins-dind docker ps
# if permission denied:
docker exec -u root jenkins-dind chmod 666 /var/run/docker.sock
docker restart jenkins-dind
```

### 18.7 Jenkins AWS credential Kind missing

Install **AWS Credentials** plugin (section 15.5).

### 18.8 Port conflicts

- App uses `5000`
- Jenkins uses `8080`
- If occupied, stop conflicting containers (`docker ps`) or remap ports.

### 18.9 Pipeline fails only on App Runner

Treat ECR success as CI artifact success; fix AWS entitlement or remove/skip deploy stage until ready.

---

## 19. Security Practices

1. **Never commit** `.env`, access-key CSVs, or PATs.  
2. Rotate any secret that was pasted into chat logs or tickets.  
3. Prefer least-privilege IAM policies over broad `*FullAccess` once project graduates.  
4. Treat FAISS pickle load as trusted-input only.  
5. Medical disclaimer: outputs are informational retrieval over an encyclopedia, **not clinical advice**.  
6. Template currently uses `| safe` on message content; for harder multi-tenant hardening, sanitize/escape model output more strictly.  
7. Jenkins and Docker socket access is powerful — keep Jenkins local/private; do not expose `:8080` to the public internet without auth hardening and network controls.  
8. Use mutable `latest` tags for learning; for production prefer immutable digests/semver tags.

---

## 20. Limitations, Design Trade-offs & Future Work

### 20.1 Current limitations

- Session memory is browser cookie/server session only (not durable multi-user history).
- Chain/model reload per request is simple but not maximizing throughput.
- Retrieval is dense-only (no hybrid BM25 + vector).
- Encyclopedia chunks can be noisy for some queries; answer quality depends on chunk boundaries.
- App Runner may be unavailable on restricted free AWS plans.
- Trivy gate is advisory, not enforcing.

### 20.2 Sensible future upgrades

- Cache embedding model + QA chain at process start.
- Add hybrid retrieval and re-ranking.
- Add source citations in UI (return `source_documents=True`).
- Enforce Trivy fail-on-HIGH.
- Pin dependency versions with lockfiles.
- Add unit/integration tests for chunking and retrieval.
- Add health endpoint `/healthz` for orchestrators.
- Replace App Runner with EC2/ECS/Lightsail if entitlement remains blocked.
- Add observability (structured logs, request IDs, latency metrics).

---

## 21. Glossary

| Term | Meaning |
|---|---|
| **RAG** | Retrieval-Augmented Generation: retrieve documents, then generate with them in context |
| **Embedding** | Numeric vector representing text meaning |
| **FAISS** | Facebook AI Similarity Search library for vector nearest neighbors |
| **Chunk** | Small text segment indexed/retrieved independently |
| **RetrievalQA** | LangChain helper chaining retriever + LLM prompt |
| **Stuff chain** | Put all retrieved docs into one prompt |
| **LLMOps** | Operational practices for LLM apps (packaging, CI/CD, eval, monitoring, deployment) |
| **ECR** | Elastic Container Registry |
| **Trivy** | Vulnerability scanner for images/filesystems |
| **App Runner** | AWS managed service to run containers with HTTPS endpoint |
| **PAT** | Personal Access Token (GitHub auth for automation) |

---

## 22. Appendix: Useful Commands Cheatsheet

```bash
# --- local app ---
python3.12 -m venv venv
source venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install --extra-index-url https://download.pytorch.org/whl/cpu -e .
cp .env.example .env
python app/application.py

# rebuild FAISS
python -m app.components.data_loader

# --- docker app ---
docker build -t medical-rag-chatbot:latest .
docker run --rm -p 5000:5000 -e GROQ_API_KEY=... medical-rag-chatbot:latest

# --- aws identity / ecr ---
aws sts get-caller-identity
aws ecr describe-repositories --region us-east-1
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/medical-rag-chatbot:latest

# --- jenkins ---
cd custom_jenkins && docker build -t jenkins-dind . && cd ..
docker run -d --name jenkins-dind --group-add $(getent group docker | cut -d: -f3) \
  -p 8080:8080 -p 50000:50000 \
  -v /var/run/docker.sock:/var/run/docker.sock -v jenkins_home:/var/jenkins_home \
  jenkins-dind
docker exec jenkins-dind cat /var/jenkins_home/secrets/initialAdminPassword
docker logs -f jenkins-dind
docker restart jenkins-dind

# --- inspect latest jenkins build log ---
docker exec jenkins-dind bash -lc 'tail -100 $(ls -1d /var/jenkins_home/jobs/medical-rag-pipeline/builds/[0-9]* | sort -n | tail -1)/log'
```

---

## Closing Summary

This project demonstrates a complete LLMOps-oriented medical RAG system:

1. **Knowledge preparation** from a medical encyclopedia PDF into FAISS.  
2. **Grounded answering** with Groq/OpenRouter and constrained prompting.  
3. **User interface** via Flask.  
4. **Packaging** as an installable Python project and Docker image.  
5. **Automation** with Jenkins + Trivy + Amazon ECR.  
6. **Optional managed deployment** to App Runner when the cloud account allows it.

If you can clone the repository, set `GROQ_API_KEY`, install CPU dependencies, and run `python app/application.py`, you have a working Medical RAG Chatbot. If you continue through Docker, Jenkins, and ECR, you have a working LLMOps delivery pipeline for that chatbot.

---

*End of report.*
