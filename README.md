# Prometheus — Autonomous ML Pipeline Builder

Prometheus takes a plain-English description of an ML problem and a CSV file, then autonomously designs, trains, debugs, evaluates, and packages a production-ready model with two human approval gates and a live in-browser test panel.

**v2 supports both binary classification and regression.**

---

## Demo results

### Binary classification

| Dataset | Accuracy | Unseen rows tested | Notes |
|---------|----------|--------------------|-------|
| Titanic (survival) | **80%** | 24 held-out | 0/1 numeric labels, NaN-heavy `Cabin` column |
| Heart disease | **88%** | 22 held-out | Numeric features, class-balanced |
| Customer churn | **75%** | 15 held-out | Yes/No string labels, full encoding round-trip |

### Regression

| Dataset | R² | RMSE % of mean | Within 20% | Notes |
|---------|-----|----------------|------------|-------|
| California housing | **0.83** | **12.4%** | **71%** | Log-transform auto-applied (skewness > 1.5) |

All results on truly held-out rows not seen during training, tested live through the prediction panel.

---

## What it does

1. **Analyzes** your problem description and infers task type (classification or regression), target column, and evaluation metric
2. **Profiles** the dataset null rates, distributions, leakage warnings, class imbalance (classification) or skewness warnings (regression)
3. **Designs** two architecturally distinct ML pipelines and runs them in parallel in isolated E2B sandboxes
4. **Debugs** failures autonomously up to 3 retry cycles per experiment with LLM-guided fixes; regenerates from scratch if the same error recurs
5. **Selects** the winning model with a written justification comparing all metrics
6. **Documents** the model card, SHAP feature importance, and plain-English explanation; regression models additionally show a Success Rate panel with tolerance-based accuracy metrics
7. **Deploys** a self-contained FastAPI prediction endpoint with a downloadable `model.pkl`

---

## Features

- **Zero-code ML** describe your problem in plain English, upload a CSV, done
- **Classification + regression** fully separate pipelines with task-appropriate agents, metrics, and UI
- **Autonomous debugging** up to 3 retries with LLM-guided fixes; regenerates from scratch on repeated failures
- **Smart preprocessing** binary encoding, one-hot encoding, NaN-consistent imputation, class balancing (classification), and automatic log-transform detection (regression)
- **Two human approval gates** review problem analysis before training; review model results before deployment
- **In-browser test panel** predict live; filter by class or test unseen held-out rows (shown as ◆)
- **Regression success metrics** R², RMSE as % of target mean, and % predictions within 10%/15%/20% tolerance, displayed as animated progress bars
- **Downloadable artifacts** `endpoint.py` + `model.pkl` for self-hosting
- **Full audit trail** every agent decision, LLM call, retry, and fix logged in the debug log
- **MLflow tracking** all experiments tracked with parameters, metrics, and code snapshots
- **Free-tier AI** Ollama (local LLMs) + Gemini free tier; no paid API required

---

## Architecture

### Microservice layout

Both task types share a **single FastAPI backend** on port 8000. The code is split into isolated modules so changes to regression never touch classification.

```
prometheus/
├── main.py              ← unified FastAPI app (port 8000)
├── celery_app.py        ← unified Celery worker
├── shared/              ← LLM router + E2B executor (imported by both)
│   ├── llm/             ← OllamaClient · GeminiClient · LLMRouter
│   └── execution/       ← E2BExecutor · CodeValidator
├── classification/      ← binary classification pipeline
│   ├── agents/          ← 10 autonomous agents (classification-specific)
│   ├── routers/         ← /classification/jobs/* endpoints
│   ├── state.py         ← ClassificationState TypedDict
│   └── ...
└── regression/          ← regression pipeline
    ├── agents/          ← 10 autonomous agents (regression-specific)
    ├── routers/         ← /regression/jobs/* endpoints
    ├── state.py         ← RegressionState TypedDict
    └── ...
```

**Key isolation rule:** `classification/` and `regression/` never import from each other. All shared utilities come exclusively from `shared/`.

### Pipeline

```
Upload CSV + description
        │
        ▼
  problem_analyzer       ← llama3.1:8b infers task type, target column, metric
        │
        ▼
  ── APPROVAL GATE 1 ──  ← user confirms / corrects task type and target
        │
        ▼
  data_profiler          ← stats, null rates, leakage detection
        │                   classification: imbalance check
        │                   regression: skewness / log-transform recommendation
        ▼
  pipeline_designer      ← llama3.1:8b proposes 2 contrasting architectures
        │
        ├──────────────────────────────────────┐
        ▼                                      ▼
  code_generator (A)                   code_generator (B)    ← deepseek-coder:6.7b
  E2B sandbox execution                E2B sandbox execution
  result_interpreter                   result_interpreter
  failure_diagnostician                failure_diagnostician
  fix_executor (×3 max)                fix_executor (×3 max)
        │                                      │
        └──────────────── JOIN ────────────────┘
                          │
                          ▼
                   model_selector    ← Gemini 1.5 Flash picks winner with justification
                          │
                          ▼
            ── APPROVAL GATE 2 ──   ← user approves winning model
                          │
                          ▼
               documentation_agent  ← model card + SHAP + plain-English explanation
                          │
                          ▼
                   output_agent     ← generates FastAPI endpoint + requirements.txt
                          │
                          ▼
                     DEPLOYED ✓
```

### LLM routing

| Task | Model | Why |
|------|-------|-----|
| Code generation / fixing | `deepseek-coder:6.7b` (Ollama) | Specialized code model |
| Problem analysis / profiling / interpretation | `llama3.1:8b` (Ollama) | General reasoning, free |
| Model selection / complex decisions | `Gemini 1.5 Flash` | Strongest reasoning, free tier |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · Framer Motion |
| Backend | FastAPI · Python 3.11+ · Celery + Redis |
| Pipeline orchestration | LangGraph StateGraph |
| Local LLMs | Ollama (`llama3.1:8b` + `deepseek-coder:6.7b`) |
| Cloud LLM | Gemini 1.5 Flash (free tier) |
| Code execution | E2B cloud sandboxes |
| ML libraries | scikit-learn · XGBoost · LightGBM · SHAP |
| Experiment tracking | MLflow |
| State persistence | SQLite (per service) |

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | Backend + Celery |
| Node.js 18+ | Frontend |
| [Ollama](https://ollama.ai) | Local LLM inference |
| [E2B API key](https://e2b.dev) | Sandbox execution free tier available |
| [Gemini API key](https://aistudio.google.com) | Free tier, 1M tokens/day |
| Docker Desktop | Redis + MLflow via `docker-compose` |

---

## Quick start

### 1. Clone and configure

```bash
git clone https://github.com/tanmay-devhub/Prometheus.git
cd Prometheus/prometheus
cp .env.example .env
# Fill in GEMINI_API_KEY and E2B_API_KEY
```

### 2. Install dependencies

```bash
# Python (from prometheus/)
pip install -r requirements.txt

# Node
cd frontend && npm install && cd ..
```

### 3. Pull Ollama models

```bash
ollama pull llama3.1:8b
ollama pull deepseek-coder:6.7b
```

### 4. Start all services

**Windows one-click:**
```
start.bat
```

**Manual (all platforms):**

```bash
# Terminal 1 Ollama
ollama serve

# Terminal 2 Redis + MLflow
docker-compose up -d

# Terminal 3 FastAPI backend (serves both classification + regression)
python -m uvicorn main:app --port 8000 --reload

# Terminal 4 Celery worker (handles both pipelines)
# Windows:
python -m celery -A celery_app worker --loglevel=info --pool=solo
# Linux / macOS:
python -m celery -A celery_app worker --loglevel=info

# Terminal 5 Frontend
cd frontend && npm run dev
```

### 5. Open the app

| Service | URL |
|---------|-----|
| **Prometheus UI** | http://localhost:3000 |
| API docs (classification) | http://localhost:8000/classification/docs |
| API docs (regression) | http://localhost:8000/regression/docs |
| MLflow UI | http://localhost:5000 |

Navigate to `http://localhost:3000`, choose **Classification** or **Regression** from the landing page, upload a CSV, and describe your problem.

---

## Preprocessing (automatic, applied identically at train and predict time)

| Step | Classification | Regression |
|------|---------------|------------|
| Numeric string repair | `"1.5"` → `float` | Same |
| Target encoding | String labels → 0/1, reversed at prediction | **Not applied** target is always numeric |
| Log transform | Not applicable | Auto-applied if target skewness > 1.5 and all values > 0; reversed with `expm1` at prediction |
| Binary feature encoding | `LabelEncoder` for 2-class string columns | Same |
| Multi-category encoding | `pd.get_dummies` with XGBoost-safe names | Same |
| Numeric imputation | Median fill (training data only) | Same |
| Class balancing | Automatic per model type (see below) | Not applicable |
| NaN consistency | `fillna("nan")` in training and prediction | Same |

### Class balancing (classification only)

| Model | Method |
|-------|--------|
| `RandomForestClassifier`, `LogisticRegression`, `LGBMClassifier` | `class_weight='balanced'` |
| `XGBClassifier` | `scale_pos_weight = n_negative / n_positive` |
| `GradientBoostingClassifier` | `compute_sample_weight('balanced', y_train)` |

---

## Regression success metrics

Every regression model is evaluated on four metrics beyond the primary score:

| Metric | Description | Good threshold |
|--------|-------------|----------------|
| **R² Score** | Variance explained (0–1) | ≥ 0.80 |
| **RMSE % of mean** | RMSE relative to target mean scale-independent | ≤ 15% |
| **Within 10% tolerance** | % of predictions with < 10% relative error | ≥ 60% |
| **Within 15% tolerance** | % of predictions with < 15% relative error | ≥ 70% |
| **Within 20% tolerance** | % of predictions with < 20% relative error | ≥ 80% |

These are computed in the E2B sandbox, stored in `model.pkl` under `training_metrics`, and displayed as animated progress bars in the **Success Rate** panel on the results page.

---

## Supported models

### Classification

| Model | Notes |
|-------|-------|
| `LogisticRegression` | Linear baseline, fast |
| `RandomForestClassifier` | Strong all-rounder |
| `GradientBoostingClassifier` | Robust to outliers |
| `XGBClassifier` | High accuracy, fast inference |
| `LGBMClassifier` | Best on large datasets |

### Regression

| Model | Notes |
|-------|-------|
| `Ridge` | Linear, handles collinearity |
| `Lasso` | Linear with L1 feature selection |
| `RandomForestRegressor` | Robust ensemble |
| `GradientBoostingRegressor` | Strong on mixed feature types |
| `XGBRegressor` | Fast, handles missing values natively |
| `LGBMRegressor` | Fastest on large datasets |

---

## Self-hosting the endpoint

Download `endpoint.py` and `model.pkl` from the results page, then:

```bash
pip install fastapi uvicorn pydantic scikit-learn xgboost lightgbm pandas numpy
uvicorn endpoint:app --host 0.0.0.0 --port 8001
```

Open **http://localhost:8001/docs** for the interactive Swagger UI.

### Classification endpoint

| Route | Description |
|-------|-------------|
| `POST /predict` | Returns `prediction` (original label), `prediction_encoded`, `probability` |
| `GET /encoding` | Inspect all column mappings |
| `GET /features` | List required input fields |
| `GET /health` | Liveness check |

### Regression endpoint

| Route | Description |
|-------|-------------|
| `POST /predict` | Returns `prediction` (float), `prediction_formatted` (e.g. `"187,432.50"`) |
| `GET /metrics` | Training metrics RMSE, MAE, R², tolerance bands |
| `GET /encoding` | Inspect feature encodings and log-transform status |
| `GET /features` | List required input fields |
| `GET /health` | Liveness check |

---

## API reference

All routes are prefixed by task type. Replace `{type}` with `classification` or `regression`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/{type}/jobs` | Create job (multipart: `file` + `description`) |
| `GET` | `/{type}/jobs/{id}` | Full job state |
| `GET` | `/{type}/jobs/{id}/status` | Current phase (for polling) |
| `GET` | `/{type}/jobs/{id}/profile` | Dataset profile report |
| `GET` | `/{type}/jobs/{id}/experiments` | Both experiment results |
| `GET` | `/{type}/jobs/{id}/debug-log` | Full agent decision log |
| `POST` | `/{type}/jobs/{id}/approve-problem` | Approve / correct problem analysis |
| `POST` | `/{type}/jobs/{id}/approve-model` | Approve winning model |
| `POST` | `/{type}/jobs/{id}/test-predict` | Live in-browser prediction |
| `GET` | `/{type}/jobs/{id}/model-card` | Model card markdown |
| `GET` | `/{type}/jobs/{id}/endpoint-code` | `endpoint.py` source + `requirements.txt` |
| `GET` | `/{type}/jobs/{id}/model.pkl` | Download trained model |
| `GET` | `/{type}/jobs/{id}/explanation` | SHAP features, justification, and metrics |

Full interactive docs: **http://localhost:8000/docs**

---

## Project structure

```
prometheus/
├── main.py                    ← unified FastAPI app (port 8000)
├── celery_app.py              ← unified Celery worker
├── shared/                    ← utilities shared by both pipelines
│   ├── llm/
│   │   ├── router.py          ← routes tasks to Ollama or Gemini
│   │   ├── ollama_client.py
│   │   └── gemini_client.py
│   ├── execution/
│   │   ├── e2b_executor.py    ← sandbox runner + output parser
│   │   └── code_validator.py  ← AST-based pre-submission checks
│   └── config.py
├── classification/            ← binary classification pipeline
│   ├── agents/                ← 10 agents (classification-specific)
│   ├── routers/               ← /classification/jobs/* endpoints
│   ├── tracking/              ← MLflow integration
│   ├── state.py               ← ClassificationState TypedDict
│   ├── graph.py               ← parallel experiment runner
│   ├── tasks.py               ← Celery task definitions
│   ├── db.py                  ← SQLite persistence
│   └── config.py
├── regression/                ← regression pipeline
│   ├── agents/                ← 10 agents (regression-specific)
│   ├── routers/               ← /regression/jobs/* endpoints
│   ├── tracking/              ← MLflow integration
│   ├── state.py               ← RegressionState TypedDict
│   ├── graph.py               ← parallel experiment runner
│   ├── tasks.py               ← Celery task definitions
│   ├── db.py                  ← SQLite persistence
│   └── config.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx           ← landing page (choose classification or regression)
│   │   ├── classification/    ← classification pipeline UI
│   │   │   └── page.tsx
│   │   ├── regression/        ← regression pipeline UI
│   │   │   └── page.tsx
│   │   └── components/
│   │       ├── (shared)       ← UploadPanel, ApprovalGate, ProfileView, etc.
│   │       └── regression/    ← RegressionTestPanel, RegressionModelCard
│   └── lib/
│       ├── classification-api.ts
│       └── regression-api.ts
├── demo_datasets/
│   ├── titanic.csv
│   └── heart_disease.csv
├── docker-compose.yml         ← Redis + MLflow
├── requirements.txt
├── start.bat                  ← Windows one-click launcher
└── .env.example
```

---

## Known limitations

- **Tabular data only** no image, text, audio, or time-series support
- **Binary classification only** multi-class classification is not yet supported
- **E2B required** experiments need an active E2B API key and internet access
- **Ollama must run locally** LLM inference is not remote; Ollama must be on the same machine as the backend
- **Windows Celery** requires `--pool=solo`; Linux/macOS can use the default `prefork` pool
- **sklearn version coupling** `model.pkl` is built inside E2B; if loading locally fails, pin `scikit-learn>=1.3.0,<2.0.0`

---

## License

MIT
