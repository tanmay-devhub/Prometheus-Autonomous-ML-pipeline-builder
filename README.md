# Prometheus — Autonomous ML Pipeline Builder

Prometheus takes a plain-English description of an ML problem and a CSV file, then autonomously builds, debugs, evaluates, and packages a production-ready ML model — with two human approval gates along the way.

---

## What it does

1. **Analyzes** your problem description and infers task type, target column, and evaluation metric
2. **Profiles** your dataset — null rates, distributions, class imbalance, leakage warnings
3. **Designs** two meaningfully different ML pipeline architectures
4. **Runs** both experiments in isolated E2B cloud sandboxes, with automatic debugging on failure
5. **Selects** the best model based on held-out metric score
6. **Generates** a deployable FastAPI endpoint and a model card
7. **Lets you test** predictions directly in the browser — no local setup needed

---

## Key Features

- **Zero-code ML** — describe your problem in plain English, upload a CSV, done
- **Autonomous debugging** — up to 3 retries per experiment with LLM-guided fixes; regenerates from scratch if stuck in a loop
- **Two human approval gates** — review problem analysis before training; review model results before deployment
- **In-browser testing** — run predictions against your trained model directly from the UI
- **Downloadable artifacts** — `endpoint.py` + `model.pkl` for self-hosting
- **Full audit trail** — every agent decision logged in the debug log
- **MLflow tracking** — all experiments tracked with parameters, metrics, and code snapshots
- **Free-tier AI** — Ollama (local LLMs) + Gemini 2.0 Flash free tier; no paid API required

---

## Architecture

```
Browser (localhost:3002)
    │
    ▼
Next.js Frontend
    │  polls /jobs/{id}/status every 3s
    ▼
FastAPI Backend (localhost:8000)
    │
    ├── Celery Worker  ←─── Redis (task queue)
    │       │
    │       ▼
    │   Agent Pipeline
    │       ├── problem_analyzer      → Ollama llama3.1:8b
    │       ├── data_profiler         → Ollama llama3.1:8b
    │       ├── pipeline_designer     → Ollama llama3.1:8b
    │       ├── code_generator        → Ollama deepseek-coder:6.7b
    │       ├── E2B Sandbox           → cloud execution
    │       ├── failure_diagnostician → Ollama llama3.1:8b
    │       ├── fix_executor          → Ollama deepseek-coder:6.7b
    │       ├── model_selector        → Gemini 2.0 Flash
    │       ├── documentation_agent   → Ollama llama3.1:8b
    │       └── output_agent          → Ollama deepseek-coder:6.7b
    │
    ├── SQLite  (job state + LLM call log)
    └── MLflow  (experiment tracking, localhost:5000)
```

### LLM Routing

| Task | Model | Why |
|------|-------|-----|
| Code generation / fixing | `deepseek-coder:6.7b` (Ollama) | Specialized code model |
| Reasoning / analysis / profiling | `llama3.1:8b` (Ollama) | General reasoning |
| Model selection / complex decisions | `gemini-2.0-flash` (API) | Best quality for critical choices |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · Recharts |
| Backend | FastAPI · Python 3.11+ · Celery · SQLAlchemy |
| Local LLMs | Ollama (`llama3.1:8b` + `deepseek-coder:6.7b`) |
| Cloud LLM | Gemini 2.0 Flash (free tier) |
| Code execution | E2B cloud sandboxes |
| ML libraries | scikit-learn · XGBoost · LightGBM · SHAP |
| Experiment tracking | MLflow |
| Task queue | Celery + Redis 7 |
| Database | SQLite |

---

## Prerequisites

| Requirement | Install |
|-------------|---------|
| Python 3.11+ | [python.org](https://python.org) |
| Node.js 18+ | [nodejs.org](https://nodejs.org) |
| Docker Desktop | [docker.com](https://docker.com) — for Redis + MLflow |
| Ollama | [ollama.ai](https://ollama.ai) — runs LLMs locally |
| Gemini API key | Free at [aistudio.google.com](https://aistudio.google.com) |
| E2B API key | Free at [e2b.dev](https://e2b.dev) |

---

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd prometheus
```

Copy the example env and fill in your keys:

```bash
cp .env.example .env
```

`.env` contents:

```env
GEMINI_API_KEY=your_gemini_api_key_here
E2B_API_KEY=your_e2b_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_REASONING_MODEL=llama3.1:8b
OLLAMA_CODE_MODEL=deepseek-coder:6.7b
GEMINI_MODEL=gemini-2.0-flash
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
REDIS_URL=redis://localhost:6379
DATABASE_URL=sqlite:///prometheus.db
MAX_RETRIES=3
E2B_TIMEOUT_SECONDS=300
```

### 2. Pull Ollama models

```bash
ollama pull llama3.1:8b
ollama pull deepseek-coder:6.7b
```

### 3. Start everything (Windows)

```bash
start.bat
```

This opens separate windows for each service. Or run manually:

```bash
# Terminal 1 — Infrastructure
docker-compose up -d

# Terminal 2 — Backend (from prometheus/ folder)
set PYTHONPATH=D:\path\to\prometheus
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --reload-dir backend --port 8000

# Terminal 3 — Celery worker (from prometheus/ folder)
set PYTHONPATH=D:\path\to\prometheus
python -m celery -A backend.celery_app worker --loglevel=info --pool=solo

# Terminal 4 — Frontend
cd frontend && npm install && npm run dev -- --port 3002
```

### 4. Open the app

| Service | URL |
|---------|-----|
| **Prometheus UI** | http://localhost:3002 |
| Backend API docs | http://localhost:8000/docs |
| MLflow UI | http://localhost:5000 |

---

## Pipeline Walkthrough

### Stage 1 — Problem Analysis *(~30 sec)*
Reads your description, infers task type (`binary_classification` / `regression`), target column, and evaluation metric. Flags potential issues.

**→ Human gate:** Review and correct before training starts.

### Stage 2 — Data Profiling *(~30 sec)*
Scans every column: null rates, distributions, class imbalance detection, potential leakage warnings, LLM-generated dataset interpretation.

### Stage 3 — Pipeline Design *(~20 sec)*
Proposes two architecturally different ML pipelines tailored to your dataset (e.g. gradient boosting vs. logistic regression, or a complex ensemble vs. a linear model).

### Stage 4 — Parallel Experiments *(2–5 min)*
Both pipelines run simultaneously in E2B cloud sandboxes:
- Generates complete Python training scripts with OrdinalEncoder + median imputation
- Validates syntax, imports, and column references before submission
- Automatic retry loop (up to 3): classifies failure → generates targeted fix
- If the same error repeats on consecutive retries, discards code and regenerates from scratch

### Stage 5 — Model Selection *(~20 sec)*
Gemini 2.0 Flash compares both experiments by metric score and writes a selection justification.

**→ Human gate:** Review results, optionally switch to the other experiment, then approve.

### Stage 6 — Documentation *(~30 sec)*
Generates a model card: algorithm, training data, performance, limitations, intended use, and how-not-to-use.

### Stage 7 — Output Generation *(~30 sec)*
Produces:
- **`endpoint.py`** — self-contained FastAPI app with `/predict`, `/health`, `/features`
- **`model.pkl`** — dict containing the trained model, category encodings, and numeric medians

---

## In-Browser Prediction Testing

After a pipeline completes, the **Test Model** panel appears on the results page. It:
- Pre-fills all feature fields with a sample row from your dataset
- Sends the values to `POST /jobs/{id}/test-predict` on the Prometheus backend
- Returns the prediction and confidence score instantly

No separate server or local dependencies needed.

---

## Self-Hosting the Endpoint

Download both files from the results page, then:

```bash
mkdir my_model && cd my_model
# Place endpoint.py and model.pkl here

pip install fastapi>=0.110.0 uvicorn>=0.29.0 pydantic>=2.0.0 \
    scikit-learn>=1.3.0 xgboost>=2.0.0 lightgbm>=4.0.0 \
    pandas>=2.0.0 numpy>=1.26.0

uvicorn endpoint:app --host 0.0.0.0 --port 8001
```

Open **http://localhost:8001/docs** for the interactive Swagger UI.

> **sklearn version note:** `model.pkl` is built inside an E2B sandbox. If you get an `AttributeError` on load, run:
> `pip install "scikit-learn>=1.3.0,<2.0.0" --upgrade`

---

## Project Structure

```
prometheus/
├── backend/
│   ├── agents/              # 10 autonomous ML agents
│   │   ├── problem_analyzer.py
│   │   ├── data_profiler.py
│   │   ├── pipeline_designer.py
│   │   ├── code_generator.py
│   │   ├── result_interpreter.py
│   │   ├── failure_diagnostician.py
│   │   ├── fix_executor.py
│   │   ├── model_selector.py
│   │   ├── documentation_agent.py
│   │   └── output_agent.py
│   ├── llm/
│   │   ├── router.py        # Routes tasks to correct LLM + fallback logic
│   │   ├── ollama_client.py
│   │   └── gemini_client.py
│   ├── routers/
│   │   ├── jobs.py          # Job CRUD, test-predict, model download
│   │   └── approvals.py     # Human approval gate endpoints
│   ├── tracking/
│   │   └── mlflow_tracker.py
│   ├── main.py              # FastAPI app entry point
│   ├── state.py             # PrometheusState TypedDict (single source of truth)
│   ├── config.py            # Environment variables
│   ├── db.py                # SQLite job persistence (NaN-safe JSON encoder)
│   ├── graph.py             # Parallel experiment runner
│   └── celery_app.py        # Celery configuration
├── execution/
│   ├── e2b_executor.py      # E2B sandbox runner + pkl retrieval via stdout
│   └── code_validator.py    # Pre-submission code checks (syntax, imports, columns)
├── frontend/
│   ├── app/
│   │   ├── components/
│   │   │   ├── UploadPanel.tsx
│   │   │   ├── ApprovalGate.tsx
│   │   │   ├── ProfileView.tsx
│   │   │   ├── ExperimentPanel.tsx
│   │   │   ├── PipelineProgress.tsx
│   │   │   ├── TestModelPanel.tsx
│   │   │   ├── ModelCard.tsx
│   │   │   ├── EndpointViewer.tsx
│   │   │   └── DebugLog.tsx
│   │   ├── page.tsx         # Main app shell with polling logic
│   │   └── layout.tsx
│   └── lib/
│       └── api.ts           # Typed API client
├── demo_datasets/
│   ├── titanic.csv          # Binary classification (target: Survived)
│   └── heart_disease.csv    # Binary classification (target: target)
├── tasks.py                 # Celery task definitions (phase-based pipeline)
├── docker-compose.yml       # Redis 7 + MLflow
├── requirements.txt         # Python dependencies
├── start.bat                # One-click Windows launcher
├── .env                     # API keys — never commit this
└── .gitignore
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/jobs` | Create job (multipart: `file` + `description`) |
| `GET` | `/jobs/{id}` | Full job state |
| `GET` | `/jobs/{id}/status` | Current phase (for polling) |
| `GET` | `/jobs/{id}/profile` | Dataset profile report |
| `GET` | `/jobs/{id}/experiments` | Both experiment results |
| `GET` | `/jobs/{id}/debug-log` | Full agent decision log |
| `POST` | `/jobs/{id}/approve-problem` | Approve problem analysis |
| `POST` | `/jobs/{id}/approve-model` | Approve model selection |
| `POST` | `/jobs/{id}/test-predict` | Run in-browser prediction |
| `GET` | `/jobs/{id}/model-card` | Model card text |
| `GET` | `/jobs/{id}/endpoint-code` | endpoint.py source |
| `GET` | `/jobs/{id}/model.pkl` | Download model.pkl |
| `GET` | `/jobs/{id}/explanation` | SHAP features + justification |

Full interactive docs: **http://localhost:8000/docs**

---

## Supported Tasks & Models

**v1 — Tabular data only**

| Task | Metric | Supported models |
|------|--------|-----------------|
| Binary classification | ROC-AUC | LogisticRegression, RandomForest, GradientBoosting, XGBoost, LightGBM |
| Regression | R², RMSE | Ridge, RandomForest, GradientBoosting, XGBoost, LightGBM |

---

## Known Limitations

- **Tabular only** — no image, text, or time-series support in v1
- **Binary classification only** — multi-class not yet supported
- **E2B required** — experiments need an active E2B key and internet access
- **Ollama must run locally** — LLMs are not called remotely; Ollama must be on the same machine
- **Windows `--pool=solo`** — Celery on Windows requires `--pool=solo`; Linux/Mac should use `--pool=prefork`
- **sklearn version coupling** — `model.pkl` is built in E2B with the latest sklearn; see note above if loading fails locally

---

## License

MIT
