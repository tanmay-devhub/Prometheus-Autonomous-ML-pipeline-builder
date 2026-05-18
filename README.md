# Prometheus: Autonomous ML Pipeline Builder

Prometheus takes a plain-English description of an ML problem and a CSV file, then autonomously builds, debugs, evaluates, and packages a production-ready ML model with two human approval gates and a live in-browser test panel.

> **v1 Binary classification only.** Regression support is planned for v2.

---

## Demo results

| Dataset | Accuracy | Unseen rows tested | Notes |
|---------|----------|--------------------|-------|
| Titanic (survival) | **80%** | 24 held-out | 0/1 numeric labels |
| Heart disease | **88%** | 22 held-out | Numeric features, class-balanced |
| Customer churn | **75%** | 15 held-out | Yes/No string labels, full encoding round-trip |

All results on truly held-out rows not seen during training, tested live through the prediction panel.

---

## What it does

1. **Analyzes** your problem description and infers task type, target column, and evaluation metric
2. **Profiles** your dataset null rates, distributions, class imbalance, leakage warnings
3. **Designs** two architecturally distinct ML pipeline architectures in parallel
4. **Executes** both pipelines in isolated E2B cloud sandboxes with automatic debugging on failure
5. **Selects** the winning model with a written justification
6. **Generates** a model card, SHAP feature importance, and plain-English explanation
7. **Deploys** a self-contained FastAPI endpoint with a downloadable `model.pkl`

---

## Features

- **Zero-code ML** describe your problem in plain English, upload a CSV, done
- **Autonomous debugging** up to 3 retries per experiment with LLM-guided fixes; regenerates from scratch if stuck in the same failure loop
- **Smart preprocessing** binary encoding, one-hot encoding, NaN-consistent imputation, and class balancing handled automatically
- **Two human approval gates** review problem analysis before training; review model results before deployment
- **In-browser test panel** predict live against your trained model; filter by class or test unseen held-out rows (shown as diamonds ◆)
- **Downloadable artifacts** `endpoint.py` + `model.pkl` for self-hosting
- **Full audit trail** every agent decision, LLM call, retry, and fix logged in the debug log
- **MLflow tracking** all experiments tracked with parameters, metrics, and code snapshots
- **Free-tier AI** Ollama (local LLMs) + Gemini free tier; no paid API required

---

## Pipeline

```
Upload CSV + description
        │
        ▼
  problem_analyzer          ← llama3.1:8b  infers task type, target column, metric
        │
        ▼
  ─── APPROVAL GATE 1 ───   ← user confirms / corrects task type and target
        │
        ▼
  data_profiler             ← stats, null rates, leakage detection, imbalance check
        │
        ▼
  pipeline_designer         ← llama3.1:8b  designs 2 contrasting architectures
        │
        ├────────────────────────────────────────────────┐
        ▼                                                ▼
  code_generator (A)                           code_generator (B)    ← deepseek-coder:6.7b
  E2B sandbox execution                        E2B sandbox execution
  result_interpreter                           result_interpreter
  failure_diagnostician                        failure_diagnostician
  fix_executor  (up to ×3)                     fix_executor  (up to ×3)
        │                                                │
        └──────────────────── JOIN ──────────────────────┘
                              │
                              ▼
                      model_selector             ← Gemini 1.5 Flash picks winner
                              │
                              ▼
                  ─── APPROVAL GATE 2 ───        ← user approves model before deployment
                              │
                              ▼
                  documentation_agent            ← model card + SHAP explanation
                              │
                              ▼
                      output_agent               ← FastAPI endpoint + requirements.txt
                              │
                              ▼
                          DEPLOYED ✓
```

### LLM routing

| Task | Model | Why |
|------|-------|-----|
| Code generation / fixing | `deepseek-coder:6.7b` (Ollama) | Specialized code model |
| Problem analysis / profiling / interpretation | `llama3.1:8b` (Ollama) | General reasoning, runs locally |
| Model selection / complex decisions | `gemini-1.5-flash` (API) | Strongest reasoning for critical choices |

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · Framer Motion · Recharts |
| Backend | FastAPI · Python 3.11+ · Celery |
| Pipeline orchestration | LangGraph StateGraph |
| Local LLMs | Ollama (`llama3.1:8b` + `deepseek-coder:6.7b`) |
| Cloud LLM | Gemini 1.5 Flash (free tier) |
| Code execution | E2B cloud sandboxes |
| ML libraries | scikit-learn · XGBoost · LightGBM · SHAP |
| Experiment tracking | MLflow |
| Task queue | Celery + Redis 7 |
| State persistence | SQLite |

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
git clone https://github.com/your-username/prometheus.git
cd prometheus
cp .env.example .env
# Edit .env fill in GEMINI_API_KEY and E2B_API_KEY
```

### 2. Install dependencies

```bash
# Python
pip install -r requirements.txt

# Node
cd frontend && npm install && cd ..
```

### 3. Pull Ollama models

```bash
ollama pull llama3.1:8b
ollama pull deepseek-coder:6.7b
```

### 4. Start services

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

# Terminal 3 FastAPI backend
uvicorn backend.main:app --reload --port 8000

# Terminal 4 Celery worker
# Windows:
celery -A backend.celery_app worker --loglevel=info --pool=solo
# Linux / macOS:
celery -A backend.celery_app worker --loglevel=info

# Terminal 5 Frontend
cd frontend && npm run dev
```

### 5. Open the app

| Service | URL |
|---------|-----|
| **Prometheus UI** | http://localhost:3000 |
| Backend API docs | http://localhost:8000/docs |
| MLflow UI | http://localhost:5000 |

---

## Preprocessing (automatic)

All preprocessing is applied identically in training and at prediction time no manual feature engineering required.

| Step | What happens |
|------|-------------|
| Numeric string repair | Columns like `"1.5"` auto-converted to float |
| Target encoding | String labels (`Yes`/`No`, `True`/`False`) mapped to 0/1; reversed at prediction time |
| Binary feature encoding | 2-class string columns encoded via `LabelEncoder` |
| Multi-category encoding | 3+ class string columns one-hot encoded; XGBoost/LightGBM-safe column names |
| Numeric imputation | Median fill computed from training data only (no leakage) |
| Class balancing | Automatic for all binary classifiers (see below) |
| NaN consistency | `fillna("nan")` applied identically in training and at prediction time |

### Class balancing

| Model | Method |
|-------|--------|
| `RandomForestClassifier`, `LogisticRegression`, `LGBMClassifier` | `class_weight='balanced'` |
| `XGBClassifier` | `scale_pos_weight = n_negative / n_positive` |
| `GradientBoostingClassifier` | `compute_sample_weight('balanced', y_train)` |

---

## Self-hosting the endpoint

Download `endpoint.py` and `model.pkl` from the results page, then:

```bash
pip install fastapi uvicorn pydantic scikit-learn xgboost lightgbm pandas numpy
uvicorn endpoint:app --host 0.0.0.0 --port 8001
```

Open **http://localhost:8001/docs** for interactive Swagger UI.

The endpoint exposes:
- `POST /predict` submit feature values, get prediction + probability + original label
- `GET /encoding` inspect how input features are encoded
- `GET /features` list required input fields
- `GET /health` liveness check

---

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/jobs` | Create job (multipart: `file` + `description`) |
| `GET` | `/jobs/{id}` | Full job state |
| `GET` | `/jobs/{id}/status` | Current phase (for polling) |
| `GET` | `/jobs/{id}/profile` | Dataset profile report |
| `GET` | `/jobs/{id}/experiments` | Both experiment results |
| `GET` | `/jobs/{id}/debug-log` | Full agent decision log |
| `POST` | `/jobs/{id}/approve-problem` | Approve / correct problem analysis |
| `POST` | `/jobs/{id}/approve-model` | Approve winning model |
| `POST` | `/jobs/{id}/test-predict` | Live in-browser prediction |
| `GET` | `/jobs/{id}/model-card` | Model card text |
| `GET` | `/jobs/{id}/endpoint-code` | `endpoint.py` source |
| `GET` | `/jobs/{id}/model.pkl` | Download trained model |
| `GET` | `/jobs/{id}/explanation` | SHAP features + justification |

Full interactive docs: **http://localhost:8000/docs**

---

## Supported models (v1)

| Model | Notes |
|-------|-------|
| `LogisticRegression` | Linear baseline, fast |
| `RandomForestClassifier` | Strong all-rounder |
| `GradientBoostingClassifier` | Robust to outliers |
| `XGBClassifier` | High accuracy, fast inference |
| `LGBMClassifier` | Best on large datasets |

---

## Project structure

```
prometheus/
├── backend/
│   ├── agents/              # 10 autonomous ML agents
│   ├── llm/                 # Router + Ollama + Gemini clients
│   ├── routers/             # FastAPI endpoints
│   ├── tracking/            # MLflow integration
│   ├── main.py
│   ├── state.py             # PrometheusState TypedDict single source of truth
│   ├── graph.py             # Parallel experiment runner
│   └── db.py                # SQLite persistence
├── execution/
│   ├── e2b_executor.py      # Sandbox runner
│   └── code_validator.py    # Pre-submission static checks
├── frontend/
│   ├── app/
│   │   ├── components/      # All React UI components
│   │   ├── lib/api.ts       # Typed backend API client
│   │   └── page.tsx         # App shell + polling logic
│   └── public/
├── demo_datasets/
│   ├── titanic.csv
│   └── heart_disease.csv
├── tests/
├── tasks.py                 # Celery pipeline task definitions
├── docker-compose.yml       # Redis + MLflow
├── requirements.txt
├── start.bat                # Windows one-click launcher
└── .env.example
```

---

## Known limitations

- **Binary classification only**  regression and multi-class are blocked in v1
- **Tabular data only** no image, text, audio, or time-series support
- **E2B required** experiments need an active E2B API key and internet access
- **Ollama must run locally** LLM inference is not remote; Ollama must be on the same machine as the backend
- **Windows Celery** requires `--pool=solo`; Linux/macOS should use the default `prefork` pool
- **sklearn version coupling** `model.pkl` is built in E2B; if loading locally fails, pin `scikit-learn>=1.3.0,<2.0.0`

---

## License

MIT
