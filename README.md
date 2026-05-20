# Prometheus: Autonomous ML Pipeline Builder

Prometheus takes a plain-English description of an ML problem and a CSV file, then autonomously designs, trains, debugs, evaluates, and packages a production-ready model with two human approval gates and a live in-browser test panel.

**v3 supports binary classification, regression, multi-class classification, and AI-powered auto-detection.**

---

## Demo results

### Binary classification

| Dataset | Accuracy | Unseen rows tested | Notes |
|---|---|---|---|
| Titanic (survival) | **80%** | 24 held-out | 0/1 numeric labels, NaN-heavy `Cabin` column |
| Heart disease | **88%** | 22 held-out | Numeric features, class-balanced |
| Customer churn | **75%** | 15 held-out | Yes/No string labels, full encoding round-trip |

### Regression

| Dataset | R² | RMSE % of mean | Within 20% | Notes |
|---|---|---|---|---|
| California housing | **0.83** | **12.4%** | **71%** | Log-transform auto-applied (skewness > 1.5) |

### Multi-class classification

| Dataset | F1 Macro | Classes | Notes |
|---|---|---|---|
| Iris species | **0.97** | 3 | setosa / versicolor / virginica, 0 retries |

All results on truly held-out rows not seen during training, tested live through the prediction panel.

---

## What it does

1. **Analyzes** your problem description and infers task type, target column, and evaluation metric
2. **Profiles** the dataset null rates, distributions, leakage warnings, class imbalance, and skewness
3. **Designs** two architecturally distinct ML pipelines and runs them in parallel in isolated E2B sandboxes
4. **Debugs** failures autonomously up to 3 retry cycles per experiment with LLM-guided fixes; regenerates from scratch if the same error recurs
5. **Selects** the winning model with a written justification comparing all metrics; user can override with the runner-up
6. **Documents** the model card, SHAP feature importance, and plain-English explanation
7. **Deploys** a self-contained FastAPI prediction endpoint with a downloadable `model.pkl`

---

## Features

- **Zero-code ML** describe your problem in plain English, upload a CSV, done
- **AI auto-detection** the new Quick Start mode detects the correct task type (classification / regression / multi-class) automatically from your data and description; no ML knowledge required
- **Three task types** binary classification, regression, and multi-class classification (3–20 categories), each in a fully isolated module
- **Autonomous debugging** up to 3 retries with LLM-guided fixes; regenerates from scratch on repeated failures
- **Smart preprocessing** binary encoding, one-hot encoding, NaN-consistent imputation, class balancing (classification), and automatic log-transform detection (regression)
- **Two human approval gates** review problem analysis before training; review model results before deployment
- **Runner-up override** on the model selection screen, both experiments are shown as interactive radio cards; click either to select it before approving
- **In-browser test panel** predict live; classification shows confidence and correct/incorrect badge; multi-class shows per-class probability bars for every class; regression shows formatted predicted value
- **Per-class F1 breakdown** multi-class results show individual F1 scores per class as animated progress bars
- **Regression success metrics** R², RMSE as % of target mean, and % predictions within 10%/15%/20% tolerance, displayed as animated progress bars
- **Dataset interpretation panel** the LLM's dataset insights are rendered as styled bullet-point cards with color-coded categories
- **Downloadable artifacts** `endpoint.py` + `model.pkl` for self-hosting
- **Full audit trail** every agent decision, LLM call, retry, and fix logged in the debug log
- **MLflow tracking** all experiments tracked with parameters, metrics, and code snapshots
- **Free-tier AI** Ollama (local LLMs) + Gemini free tier; no paid API required

---

## Architecture

### Microservice layout

All three task types share a **single FastAPI backend** on port 8000. Each task type lives in a completely isolated Python module changes to one never affect the others. Shared utilities (LLM router, E2B executor) are imported exclusively from `shared/`.

```
prometheus/
├── main.py                   ← unified FastAPI app (port 8000)
├── celery_app.py             ← unified Celery worker
├── auto/                     ← AI auto-detection router
│   └── router.py             ← POST /auto/jobs detects task type, routes to correct service
├── shared/                   ← LLM router + E2B executor (imported by all services)
│   ├── llm/                  ← OllamaClient · GeminiClient · LLMRouter
│   └── execution/            ← E2BExecutor · CodeValidator
├── classification/           ← binary classification pipeline
│   ├── agents/               ← 10 autonomous agents
│   ├── routers/              ← /classification/jobs/* endpoints
│   ├── state.py              ← ClassificationState TypedDict
│   └── ...
├── regression/               ← regression pipeline
│   ├── agents/               ← 10 autonomous agents
│   ├── routers/              ← /regression/jobs/* endpoints
│   ├── state.py              ← RegressionState TypedDict
│   └── ...
└── multiclassification/      ← multi-class classification pipeline (NEW in v3)
    ├── agents/               ← 10 autonomous agents
    ├── routers/              ← /multiclassification/jobs/* endpoints
    ├── state.py              ← MultiClassState TypedDict
    └── ...
```

**Key isolation rule:** `classification/`, `regression/`, and `multiclassification/` never import from each other. All shared utilities come exclusively from `shared/`.

### Pipeline

```
Upload CSV + description  (or use Quick Start AI chooses the task type)
        │
        ▼
  problem_analyzer       ← llama3.1:8b infers task type, target column, metric
        │
        ▼
  ── APPROVAL GATE 1 ──  ← user confirms / corrects task type and target
        │
        ▼
  data_profiler          ← stats, null rates, leakage detection
        │                   classification/multiclass: imbalance check + per-class counts
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
            ── APPROVAL GATE 2 ──   ← user approves (or overrides to runner-up)
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
|---|---|---|
| Code generation / fixing | `deepseek-coder:6.7b` (Ollama) | Specialized code model |
| Problem analysis / profiling / interpretation | `llama3.1:8b` (Ollama) | General reasoning, free |
| Auto task-type detection | `llama3.1:8b` (Ollama) | Fast column/description analysis |
| Model selection / complex decisions | `Gemini 1.5 Flash` | Strongest reasoning, free tier |

---

## Stack

| Layer | Technology |
|---|---|
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
|---|---|
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

# Terminal 3 FastAPI backend (serves all three pipelines + auto-detect)
python -m uvicorn main:app --port 8000 --reload

# Terminal 4 Celery worker (handles all pipelines)
# Windows:
python -m celery -A celery_app worker --loglevel=info --pool=solo
# Linux / macOS:
python -m celery -A celery_app worker --loglevel=info

# Terminal 5 Frontend
cd frontend && npm run dev
```

### 5. Open the app

| Service | URL |
|---|---|
| **Prometheus UI** | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| MLflow UI | http://localhost:5000 |

Navigate to `http://localhost:3000`:
- **Know your task?** Choose Classification, Regression, or Multi-Class from the landing cards.
- **Not sure?** Use the **Quick Start** panel describe your goal, upload a CSV, and the AI detects the correct task type and routes you automatically.

---

## Quick Start (AI auto-detection)

The Quick Start panel on the landing page removes the need to understand ML task types:

1. Enter a plain-English description of what you want to predict
2. Upload your CSV
3. Click **Analyze & Build**

The system will:
- Read the column names and sample rows
- Use `llama3.1:8b` to infer whether the problem is binary classification, multi-class classification, or regression
- Create the job in the appropriate pipeline
- Display the detected task type with reasoning and confidence
- Automatically redirect to the pipeline page with the job already running

The `POST /auto/jobs` endpoint handles the detection and routing; no additional setup is required.

---

## Preprocessing (automatic, applied identically at train and predict time)

| Step | Classification | Multi-Class | Regression |
|---|---|---|---|
| Numeric string repair | `"1.5"` → `float` | Same | Same |
| Target encoding | String labels → 0/1, reversed at prediction | LabelEncoder (all classes) | **Not applied** |
| Log transform | Not applicable | Not applicable | Auto-applied if skewness > 1.5 and all values > 0; reversed with `expm1` |
| Binary feature encoding | `LabelEncoder` for 2-class string columns | Same | Same |
| Multi-category encoding | `pd.get_dummies` with XGBoost-safe names | Same | Same |
| Numeric imputation | Median fill (training data only) | Same | Same |
| Class balancing | Automatic per model type | `class_weight='balanced'` | Not applicable |
| NaN consistency | `fillna("nan")` in training and prediction | Same | Same |

### Class balancing (classification and multi-class)

| Model | Method |
|---|---|
| `RandomForestClassifier`, `LogisticRegression`, `LGBMClassifier` | `class_weight='balanced'` |
| `XGBClassifier` | `scale_pos_weight` (binary) or omitted with sample weights |
| `GradientBoostingClassifier` | `compute_sample_weight('balanced', y_train)` |

---

## Regression success metrics

| Metric | Description | Good threshold |
|---|---|---|
| **R² Score** | Variance explained (0–1) | ≥ 0.80 |
| **RMSE % of mean** | RMSE relative to target mean scale-independent | ≤ 15% |
| **Within 10% tolerance** | % of predictions with < 10% relative error | ≥ 60% |
| **Within 15% tolerance** | % of predictions with < 15% relative error | ≥ 70% |
| **Within 20% tolerance** | % of predictions with < 20% relative error | ≥ 80% |

---

## Multi-class success metrics

| Metric | Description | Good threshold |
|---|---|---|
| **F1 Macro** | Unweighted mean F1 across all classes | ≥ 0.85 |
| **F1 Weighted** | Class-frequency-weighted mean F1 | ≥ 0.80 |
| **Accuracy** | Overall fraction of correct predictions | ≥ 0.85 |
| **Per-class F1** | Individual F1 for each class | ≥ 0.50 per class |

A "struggling class" warning is raised if any single class F1 falls below 0.50, even when overall F1 is acceptable.

---

## Supported models

### Binary classification

| Model | Notes |
|---|---|
| `LogisticRegression` | Linear baseline, fast |
| `RandomForestClassifier` | Strong all-rounder |
| `GradientBoostingClassifier` | Robust to outliers |
| `XGBClassifier` | High accuracy, fast inference |
| `LGBMClassifier` | Best on large datasets |

### Multi-class classification

| Model | Notes |
|---|---|
| `LogisticRegression` | `multi_class='multinomial'`, `solver='lbfgs'` |
| `RandomForestClassifier` | Robust ensemble, handles imbalance |
| `GradientBoostingClassifier` | Strong on mixed feature types |
| `XGBClassifier` | `objective='multi:softprob'`, fast |
| `LGBMClassifier` | `objective='multiclass'`, fastest on large datasets |

### Regression

| Model | Notes |
|---|---|
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
|---|---|
| `POST /predict` | Returns `prediction` (original label), `prediction_encoded`, `probability` |
| `GET /encoding` | Inspect all column mappings |
| `GET /features` | List required input fields |
| `GET /health` | Liveness check |

### Regression endpoint

| Route | Description |
|---|---|
| `POST /predict` | Returns `prediction` (float), `prediction_formatted` |
| `GET /metrics` | Training metrics RMSE, MAE, R², tolerance bands |
| `GET /encoding` | Inspect feature encodings and log-transform status |
| `GET /features` | List required input fields |
| `GET /health` | Liveness check |

### Multi-class endpoint

| Route | Description |
|---|---|
| `POST /predict` | Returns `prediction`, `confidence`, `all_probabilities` (dict of all classes) |
| `GET /classes` | Class names and label-to-int mapping |
| `GET /metrics` | F1 macro, F1 weighted, accuracy, per-class F1 |
| `GET /encoding` | Feature encodings |
| `GET /features` | List required input fields |
| `GET /health` | Liveness check |

---

## API reference

All pipeline routes are prefixed by task type. Replace `{type}` with `classification`, `regression`, or `multiclassification`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auto/jobs` | Auto-detect task type and create job (multipart: `file` + `description`) |
| `POST` | `/{type}/jobs` | Create job for a specific pipeline |
| `GET` | `/{type}/jobs/{id}` | Full job state |
| `GET` | `/{type}/jobs/{id}/status` | Current phase (for polling) |
| `GET` | `/{type}/jobs/{id}/profile` | Dataset profile report |
| `GET` | `/{type}/jobs/{id}/experiments` | Both experiment results |
| `GET` | `/{type}/jobs/{id}/debug-log` | Full agent decision log |
| `POST` | `/{type}/jobs/{id}/approve-problem` | Approve / correct problem analysis |
| `POST` | `/{type}/jobs/{id}/approve-model` | Approve winning model (optional: override with runner-up) |
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
├── main.py                        ← unified FastAPI app (port 8000, v3)
├── celery_app.py                  ← unified Celery worker (all three pipelines)
├── auto/
│   └── router.py                  ← POST /auto/jobs AI task-type detection + routing
├── shared/
│   ├── llm/
│   │   ├── router.py              ← routes tasks to Ollama or Gemini
│   │   ├── ollama_client.py
│   │   └── gemini_client.py
│   ├── execution/
│   │   ├── e2b_executor.py        ← sandbox runner + output parser (captures all metric types)
│   │   └── code_validator.py
│   └── config.py
├── classification/                ← binary classification pipeline
│   ├── agents/                    ← 10 agents
│   ├── routers/                   ← /classification/jobs/* endpoints
│   ├── tracking/
│   ├── state.py                   ← ClassificationState TypedDict
│   ├── graph.py
│   ├── tasks.py
│   ├── db.py
│   └── config.py
├── regression/                    ← regression pipeline
│   ├── agents/
│   ├── routers/
│   ├── tracking/
│   ├── state.py                   ← RegressionState TypedDict
│   ├── graph.py
│   ├── tasks.py
│   ├── db.py
│   └── config.py
├── multiclassification/           ← multi-class classification pipeline (v3)
│   ├── agents/                    ← 10 agents (multiclass-specific prompts and metrics)
│   ├── routers/                   ← /multiclassification/jobs/* endpoints
│   ├── tracking/
│   ├── state.py                   ← MultiClassState TypedDict
│   ├── graph.py
│   ├── tasks.py
│   ├── db.py
│   └── config.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx               ← landing page (3 task cards + Quick Start AI panel)
│   │   ├── classification/
│   │   │   └── page.tsx
│   │   ├── regression/
│   │   │   └── page.tsx
│   │   ├── multiclassification/   ← new in v3
│   │   │   └── page.tsx
│   │   └── components/
│   │       ├── ApprovalGate.tsx   ← supports all 3 task types in dropdown
│   │       ├── ModelSelectionView.tsx  ← two-card radio UI, runner-up override
│   │       ├── ProfileView.tsx    ← styled dataset interpretation cards
│   │       ├── TestModelPanel.tsx ← binary classification test panel
│   │       ├── ExperimentPanel.tsx
│   │       ├── regression/
│   │       │   ├── RegressionModelCard.tsx
│   │       │   └── RegressionTestPanel.tsx
│   │       └── multiclassification/
│   │           ├── MultiClassModelCard.tsx   ← per-class F1 bars
│   │           └── PredictionTester.tsx      ← all-class probability bars
│   └── lib/
│       ├── classification-api.ts
│       ├── regression-api.ts
│       ├── multiclassification-api.ts  ← new in v3
│       └── auto-api.ts                ← new in v3
├── demo_datasets/
│   ├── titanic.csv
│   └── heart_disease.csv
├── docker-compose.yml
├── requirements.txt
├── start.bat
└── .env.example
```

---

## Changelog

### v3.0 (current)
- **Multi-class classification pipeline** full 10-agent pipeline supporting 3–20 categories; LabelEncoder target handling; per-class F1 stored in pkl; `all_probabilities` on every prediction
- **AI auto-detection (Quick Start)** `POST /auto/jobs` detects task type from data + description via LLM; routes to the correct pipeline; frontend shows detected type with reasoning and confidence before redirect
- **Runner-up model override** model selection screen redesigned as two interactive radio cards; click either experiment to select it before approving
- **Dataset interpretation cards** LLM bullet points rendered as styled, color-coded insight cards instead of raw text
- **Landing page scrollable** page now scrolls naturally; Quick Start panel visible below task cards
- **ApprovalGate extended** multiclass_classification task type option with appropriate metric choices (F1 macro/weighted, accuracy, log-loss)
- **`/auto/jobs` endpoint** new backend route in isolated `auto/` module
- **`?job=<id>` URL routing** all three pipeline pages accept a pre-created job ID via query param, enabling post-auto-detect redirect

### v2.0
- **Regression pipeline** full 10-agent pipeline with log-transform detection, success rate panel (R², RMSE%, tolerance bands), regression-specific test panel
- **Unified backend** single FastAPI app on port 8000, single Celery worker; classification and regression isolated in separate modules
- **Regression success metrics** R², RMSE as % of mean, within-10/15/20% tolerance computed in E2B sandbox and stored in pkl

### v1.0
- Binary classification pipeline with 10 autonomous agents
- LangGraph StateGraph orchestration
- E2B sandbox code execution with up to 3 retry cycles
- Two human approval gates
- SHAP feature importance, model card generation
- FastAPI endpoint + model.pkl download
- MLflow experiment tracking

---

## Known limitations

- **Tabular data only** no image, text, audio, or time-series support
- **Multi-class range** targets with more than 20 unique values trigger a warning; use regression or manual binning
- **E2B required** experiments need an active E2B API key and internet access
- **Ollama must run locally** LLM inference is not remote; Ollama must be on the same machine as the backend
- **Windows Celery** requires `--pool=solo`; Linux/macOS can use the default `prefork` pool
- **sklearn version coupling** `model.pkl` is built inside E2B; if loading locally fails, pin `scikit-learn>=1.3.0,<2.0.0`

---

## License

MIT
