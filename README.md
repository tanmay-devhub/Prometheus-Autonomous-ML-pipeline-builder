# Prometheus: Autonomous ML Pipeline Builder

Prometheus takes a plain-English description of an ML problem and a CSV file, then autonomously designs, trains, debugs, evaluates, and packages a production-ready model with two human approval gates and a live in-browser results panel.

**v4 supports binary classification, regression, multi-class classification, time series forecasting, and AI-powered auto-detection.**

---

## Demo results

### Binary classification

| Dataset | Accuracy | Unseen rows tested | Notes |
|---|---|---|---|
| Titanic (survival) | **80%** | 24 held-out | 0/1 numeric labels, NaN-heavy `Cabin` column |
| Heart disease | **91%** | 22 held-out | Numeric features, class-balanced |
| Customer churn | **75%** | 15 held-out | Yes/No string labels, full encoding round-trip |

### Regression

| Dataset | R² | RMSE % of mean | Within 20% | Notes |
|---|---|---|---|---|
| California housing | **0.83** | **12.4%** | **71%** | Log-transform auto-applied (skewness > 1.5) |

### Multi-class classification

| Dataset | F1 Macro | Classes | Notes |
|---|---|---|---|
| Iris species | **0.97** | 3 | setosa / versicolor / virginica, 0 retries |

### Time series forecasting

| Dataset | MAPE | RMSE | MAE | Horizon | Notes |
|---|---|---|---|---|---|
| Air Passengers (monthly) | **6.4%** | **33.98** | **28.79** | 12 months | Classic seasonal dataset 1949–1960; Experiment B (RMSE 33.98) beat Experiment A (RMSE 69.32); forecast captures upward trend and seasonal pattern |

All results on truly held-out rows / test periods not seen during training, tested live through the results panel.

---

## What it does

1. **Analyzes** your problem description and infers task type, target column, evaluation metric, and (for time series) date column and forecast horizon
2. **Profiles** the dataset: null rates, distributions, leakage warnings, class imbalance, skewness, and (for time series) stationarity (ADF test), trend (R²), and seasonality (autocorrelation)
3. **Designs** two architecturally distinct ML pipelines and runs them in parallel in isolated E2B sandboxes
4. **Debugs** failures autonomously up to 3 retry cycles per experiment with LLM-guided fixes; regenerates from scratch if the same error recurs
5. **Selects** the winning model with a written justification comparing all metrics; user can override with the runner-up
6. **Documents** the model card, SHAP feature importance, and plain-English explanation
7. **Deploys** a self-contained FastAPI endpoint — classification/regression: `POST /predict`; time series: `GET /forecast`, `GET /history`, `POST /predict`

---

## Features

- **Zero-code ML**: describe your problem in plain English, upload a CSV, done
- **AI auto-detection**: the Quick Start panel detects task type (classification / regression / multi-class / time series) automatically from your data and description; no ML knowledge required
- **Four task types**: binary classification, regression, multi-class classification (3–20 categories), and time series forecasting, each in a fully isolated module
- **Autonomous debugging**: up to 3 retries with LLM-guided fixes; regenerates from scratch on repeated failures
- **Smart preprocessing**: binary encoding, one-hot encoding, NaN-consistent imputation, class balancing, and automatic log-transform detection (regression)
- **Time series feature engineering**: automatic lag features (t-1 through t-14), rolling means (7-day, 30-day), rolling std, and date features (day-of-week, month, quarter, is-weekend); always chronological split, never random
- **Two human approval gates**: review problem analysis before training; review model results before deployment
- **Runner-up override**: model selection screen shows both experiments as interactive radio cards; click either to select it before approving
- **Forecast chart**: Recharts line chart showing blue (train actuals), green (test predictions), and orange dashed (forward forecast beyond the dataset) with a vertical train/test split line
- **Forecast table**: next N predicted values with dates in a downloadable CSV table
- **In-browser test panel**: classification shows confidence and correct/incorrect badge; multi-class shows per-class probability bars; regression shows formatted predicted value
- **Per-class F1 breakdown**: multi-class results show individual F1 scores per class as animated progress bars
- **Regression success metrics**: R², RMSE as % of target mean, and % predictions within 10%/15%/20% tolerance
- **Dataset interpretation panel**: LLM insights rendered as styled, color-coded bullet-point cards
- **Downloadable artifacts**: `endpoint.py` + `model.pkl` for self-hosting
- **Full audit trail**: every agent decision, LLM call, retry, and fix logged in the debug log
- **MLflow tracking**: all experiments tracked with parameters, metrics, and code snapshots
- **Free-tier AI**: Ollama (local LLMs) + Gemini free tier; no paid API required

---

## Architecture

### Microservice layout

All four task types share a **single FastAPI backend** on port 8000. Each task type lives in a completely isolated Python module changes to one never affect the others. Shared utilities (LLM router, E2B executor) are imported exclusively from `shared/`.

```
prometheus/
├── main.py                   ← unified FastAPI app (port 8000, v4)
├── celery_app.py             ← unified Celery worker (all four pipelines)
├── auto/                     ← AI auto-detection router
│   └── router.py             ← POST /auto/jobs detects task type, routes to correct service
├── shared/                   ← LLM router + E2B executor (imported by all services)
│   ├── llm/                  ← OllamaClient · GeminiClient · LLMRouter
│   └── execution/            ← E2BExecutor (captures FORECAST: + metric JSON) · CodeValidator
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
├── multiclassification/      ← multi-class classification pipeline
│   ├── agents/               ← 10 autonomous agents
│   ├── routers/              ← /multiclassification/jobs/* endpoints
│   ├── state.py              ← MultiClassState TypedDict
│   └── ...
└── timeseries/               ← time series forecasting pipeline (NEW in v4)
    ├── agents/               ← 10 autonomous agents
    ├── routers/              ← /timeseries/jobs/* endpoints
    ├── state.py              ← TimeSeriesState TypedDict
    └── ...
```

**Key isolation rule:** `classification/`, `regression/`, `multiclassification/`, and `timeseries/` never import from each other. All shared utilities come exclusively from `shared/`.

### Pipeline

```
Upload CSV + description  (or use Quick Start AI chooses the task type)
        │
        ▼
  problem_analyzer       ← llama3.1:8b infers task type, target column, metric
                            timeseries: also detects date column, frequency, horizon
        │
        ▼
  ── APPROVAL GATE 1 ──  ← user confirms / corrects (timeseries: date col + forecast horizon)
        │
        ▼
  data_profiler          ← stats, null rates, leakage detection
                            classification/multiclass: imbalance check + per-class counts
                            regression: skewness / log-transform recommendation
                            timeseries: ADF stationarity · trend R² · seasonality autocorr · gap check
        │
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
                                       timeseries: lower RMSE wins
                          │
                          ▼
            ── APPROVAL GATE 2 ──   ← user approves (or overrides to runner-up)
                          │
                          ▼
               documentation_agent  ← model card + SHAP + plain-English explanation
                          │
                          ▼
                   output_agent     ← generates FastAPI endpoint + requirements.txt
                                       timeseries: generates forecast dates beyond dataset
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
| Frontend | Next.js 14 · TypeScript · Tailwind CSS · Framer Motion · Recharts |
| Backend | FastAPI · Python 3.11+ · Celery + Redis |
| Pipeline orchestration | LangGraph StateGraph |
| Local LLMs | Ollama (`llama3.1:8b` + `deepseek-coder:6.7b`) |
| Cloud LLM | Gemini 1.5 Flash (free tier) |
| Code execution | E2B cloud sandboxes |
| ML libraries | scikit-learn · XGBoost · LightGBM · SHAP · statsmodels |
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
git clone https://github.com/tanmay-devhub/Prometheus-Autonomous-ML-pipeline-builder.git
cd Prometheus-Autonomous-ML-pipeline-builder
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

# Terminal 3 FastAPI backend (serves all four pipelines + auto-detect)
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
- **Know your task?** Choose Classification, Regression, Multi-Class, or Time Series from the landing cards.
- **Not sure?** Use the **Quick Start** panel describe your goal, upload a CSV, and the AI detects the correct task type and routes you automatically.

---

## Quick Start (AI auto-detection)

The Quick Start panel on the landing page removes the need to understand ML task types:

1. Enter a plain-English description of what you want to predict
2. Upload your CSV
3. Click **Analyze & Build**

The system will:
- Read the column names and sample rows
- Use `llama3.1:8b` to infer whether the problem is binary classification, multi-class classification, regression, or time series forecasting
- Create the job in the appropriate pipeline
- Display the detected task type with reasoning and confidence
- Automatically redirect to the pipeline page with the job already running

The `POST /auto/jobs` endpoint handles the detection and routing; no additional setup is required.

---

## Preprocessing (automatic, applied identically at train and predict time)

| Step | Classification | Multi-Class | Regression | Time Series |
|---|---|---|---|---|
| Numeric string repair | `"1.5"` → `float` | Same | Same | Same |
| Target encoding | String labels → 0/1, reversed at prediction | LabelEncoder (all classes) | **Not applied** | **Not applied** |
| Log transform | Not applicable | Not applicable | Auto-applied if skewness > 1.5 | Not applicable |
| Binary feature encoding | `LabelEncoder` for 2-class string columns | Same | Same | Not applicable |
| Multi-category encoding | `pd.get_dummies` with XGBoost-safe names | Same | Same | Not applicable |
| Numeric imputation | Median fill (training data only) | Same | Same | Via rolling/lag features |
| Class balancing | Automatic per model type | `class_weight='balanced'` | Not applicable | Not applicable |
| Train/test split | Stratified random 80/20 | Stratified random 80/20 | Random 80/20 | **Chronological 80/20** (never random) |
| Lag features | Not applicable | Not applicable | Not applicable | t-1, t-2, t-3, t-7, t-14 |
| Rolling features | Not applicable | Not applicable | Not applicable | 7-day mean/std, 30-day mean |
| Date features | Not applicable | Not applicable | Not applicable | day-of-week, month, quarter, day-of-year, is-weekend |

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

## Time series success metrics

| Metric | Description | Good threshold |
|---|---|---|
| **MAPE** | Mean absolute percentage error most intuitive | ≤ 10% excellent · ≤ 20% good · ≤ 30% acceptable |
| **RMSE** | Root mean squared error | Lower is better; compare as % of target mean |
| **MAE** | Mean absolute error | Lower is better; same scale as the target |

The model card always includes a plain-English sentence: *"On average, predictions are X% away from actual values."*

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

### Time series forecasting

| Model | Notes |
|---|---|
| `XGBRegressor` | Gradient boosting with lag features most robust for complex patterns |
| `LGBMRegressor` | Fast gradient boosting, good on longer series |
| `RandomForestRegressor` | Strong ensemble, resistant to overfitting |
| `LinearRegression` | Baseline fast, interpretable |
| `Ridge` | Regularized linear better than LinearRegression when features are collinear |

All time series models use identical feature engineering: lag features, rolling statistics, and date components.

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

### Time series endpoint

| Route | Description |
|---|---|
| `GET /history` | Historical actuals + test-set predictions for chart rendering |
| `GET /forecast` | Pre-computed forward forecast beyond the dataset |
| `POST /predict` | Accepts `recent_values: [float]` and returns the next-step prediction |
| `GET /info` | Model type, target/date columns, frequency, horizon, and metrics |
| `GET /health` | Liveness check |

---

## API reference

All pipeline routes are prefixed by task type. Replace `{type}` with `classification`, `regression`, `multiclassification`, or `timeseries`.

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
| `POST` | `/{type}/jobs/{id}/test-predict` | Live in-browser prediction (classification / regression / multi-class) |
| `GET` | `/timeseries/jobs/{id}/forecast` | Forward forecast values and dates |
| `GET` | `/timeseries/jobs/{id}/history` | Train/test actuals + predictions for chart |
| `GET` | `/{type}/jobs/{id}/model-card` | Model card markdown |
| `GET` | `/{type}/jobs/{id}/endpoint-code` | `endpoint.py` source + `requirements.txt` |
| `GET` | `/{type}/jobs/{id}/model.pkl` | Download trained model |
| `GET` | `/{type}/jobs/{id}/explanation` | SHAP features, justification, and metrics |

Full interactive docs: **http://localhost:8000/docs**

---

## Project structure

```
prometheus/
├── main.py                        ← unified FastAPI app (port 8000, v4)
├── celery_app.py                  ← unified Celery worker (all four pipelines)
├── start.sh                       ← one-command startup script
├── auto/
│   └── router.py                  ← POST /auto/jobs AI task-type detection + routing
├── shared/
│   ├── llm/
│   │   ├── router.py              ← routes tasks to Ollama or Gemini
│   │   ├── ollama_client.py
│   │   └── gemini_client.py
│   ├── execution/
│   │   ├── e2b_executor.py        ← sandbox runner; captures __MODEL_PKL__: and FORECAST: markers
│   │   └── code_validator.py
│   └── config.py
├── classification/                ← binary classification pipeline
│   ├── agents/                    ← 10 agents
│   ├── routers/                   ← /classification/jobs/* endpoints
│   ├── tracking/
│   ├── state.py
│   ├── graph.py
│   ├── tasks.py
│   ├── db.py
│   └── config.py
├── regression/                    ← regression pipeline
│   ├── agents/
│   ├── routers/
│   ├── tracking/
│   ├── state.py
│   ├── graph.py
│   ├── tasks.py
│   ├── db.py
│   └── config.py
├── multiclassification/           ← multi-class classification pipeline
│   ├── agents/
│   ├── routers/
│   ├── tracking/
│   ├── state.py
│   ├── graph.py
│   ├── tasks.py
│   ├── db.py
│   └── config.py
├── timeseries/                    ← time series forecasting pipeline (NEW in v4)
│   ├── agents/                    ← 10 agents (chronological split, lag features, MAPE)
│   ├── routers/                   ← /timeseries/jobs/* + /forecast + /history
│   ├── tracking/
│   ├── state.py                   ← TimeSeriesState (date_column, forecast_horizon, etc.)
│   ├── graph.py
│   ├── tasks.py
│   ├── db.py
│   ├── main.py                    ← standalone service (port 8004)
│   └── config.py
├── gateway/
│   └── main.py                    ← HTTP proxy routing to all four microservices
├── frontend/
│   ├── app/
│   │   ├── page.tsx               ← landing page (4 task cards + Quick Start AI panel)
│   │   ├── classification/page.tsx
│   │   ├── regression/page.tsx
│   │   ├── multiclassification/page.tsx
│   │   ├── timeseries/page.tsx    ← new in v4
│   │   └── components/
│   │       ├── ApprovalGate.tsx
│   │       ├── ModelSelectionView.tsx   ← two-card radio UI, runner-up override
│   │       ├── ProfileView.tsx          ← styled dataset interpretation cards
│   │       ├── ExperimentPanel.tsx
│   │       ├── regression/
│   │       │   ├── RegressionModelCard.tsx
│   │       │   └── RegressionTestPanel.tsx
│   │       ├── multiclassification/
│   │       │   ├── MultiClassModelCard.tsx
│   │       │   └── PredictionTester.tsx
│   │       └── timeseries/              ← new in v4
│   │           ├── TimeSeriesApprovalGate.tsx
│   │           ├── ForecastChart.tsx    ← Recharts line chart (actuals · predictions · forecast)
│   │           ├── ForecastPanel.tsx    ← forecast values table with CSV download
│   │           └── TimeSeriesModelCard.tsx
│   └── lib/
│       ├── classification-api.ts
│       ├── regression-api.ts
│       ├── multiclassification-api.ts
│       ├── timeseries-api.ts       ← new in v4
│       └── auto-api.ts
├── demo_datasets/
│   ├── titanic.csv
│   └── heart_disease.csv
├── docker-compose.yml
├── requirements.txt
├── start.bat
├── start.sh
└── .env.example
```

---

## Testing

Nine ready-made test cases covering all four task types. Download the CSV first, then upload to Prometheus with the prompt below.

### Binary classification

| Test | Dataset | Prompt | Approval screen | Expected |
|---|---|---|---|---|
| 1 | [Titanic survival](https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv) | `Predict whether a passenger survived the Titanic disaster. Target column is Survived (1 = survived, 0 = died).` | Binary Classification · Survived · ROC-AUC | ROC-AUC > 0.80 · predictions return 0 or 1 with probability |
| 2 | [Heart disease](https://raw.githubusercontent.com/sharmaroshan/Heart-UCI-Dataset/master/heart.csv) | `Predict whether a patient has heart disease based on clinical measurements. Target column is target (1 = disease, 0 = no disease).` | Binary Classification · target · ROC-AUC | Accuracy > 85% · confidence > 80% on predictions |
| 3 | [Customer churn](https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv) | `Predict whether a telecom customer will churn and cancel their subscription. Target column is Churn.` | Binary Classification · Churn · ROC-AUC | Churn column correctly encoded · predictions return Yes/No not 0/1 |

### Regression

| Test | Dataset | Prompt | Approval screen | Expected |
|---|---|---|---|---|
| 4 | [California housing](https://raw.githubusercontent.com/ageron/handson-ml/master/datasets/housing/housing.csv) | `Predict the median house value for California districts based on demographic and geographic features. Target column is median_house_value.` | Regression · median_house_value · RMSE | RMSE < $60,000 · predictions return dollar amounts · R² > 0.75 |

### Multi-class classification

| Test | Dataset | Prompt | Approval screen | Expected |
|---|---|---|---|---|
| 5 | [Iris species](https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv) | `Classify iris flowers into one of three species based on petal and sepal measurements. Target column is species.` | Multiclass Classification · species · F1 Macro | F1 Macro > 0.95 · all 3 class probabilities shown · setosa at 100% confidence |
| 6 | [Wine quality](https://raw.githubusercontent.com/dsrscientist/dataset1/master/winequality-red.csv) | `Classify red wine quality as poor, average, or good based on chemical properties. Target column is quality. Bin scores: 1-4=poor, 5-6=average, 7-10=good.` | Multiclass Classification · quality · F1 Macro | F1 Macro 0.70–0.80 · tests class imbalance handling |

### Time series forecasting

| Test | Dataset | Prompt | Approval screen | Expected |
|---|---|---|---|---|
| 7 | [Air Passengers](https://raw.githubusercontent.com/jbrownlee/Datasets/master/airline-passengers.csv) | `Forecast monthly airline passenger numbers for the next 12 months. Date column is Month, target column is Passengers.` | Time Series · Month · Passengers · Horizon: 12 · MAPE | MAPE < 15% · forecast chart shows blue/green/orange lines · 12-month table with CSV download |
| 8 | [Daily temperature](https://raw.githubusercontent.com/jbrownlee/Datasets/master/daily-min-temperatures.csv) | `Forecast daily minimum temperature for the next 30 days. Date column is Date, target column is Temp.` | Time Series · Date · Temp · Horizon: 30 · MAPE | MAPE < 20% · tests daily frequency detection |
| 9 | [Monthly car sales](https://raw.githubusercontent.com/jbrownlee/Datasets/master/monthly-car-sales.csv) | `Forecast monthly car sales for the next 6 months. Date column is Month, target column is Sales.` | Time Series · Month · Sales · Horizon: 6 · MAPE | MAPE < 25% · tests trend + seasonality detection |

### Sanity checks

| Check | Binary | Regression | Multi-class | Time Series |
|---|---|---|---|---|
| Metric shown | ROC-AUC / Accuracy | RMSE / R² | F1 Macro | MAPE / RMSE |
| Prediction format | 0/1 or Yes/No | Dollar amount | Class name + all probabilities | Future values + chart |
| Should NOT show | RMSE or dollar amounts | ROC-AUC or Yes/No | Single confidence only | Yes/No or 0/1 |

### Gateway health check

```bash
curl http://localhost:8000/health
```

Expected: `{"classification":"healthy","regression":"healthy","multiclassification":"healthy","timeseries":"healthy"}`

---

## Changelog

### v4.0 (current)

- **Time series forecasting pipeline**: full 10-agent pipeline for sequential data; chronological train/test split (never random); automatic lag features (t-1…t-14), rolling statistics, and date features; MAPE, RMSE, and MAE metrics; recursive N-step forward forecast beyond the dataset
- **Forecast chart**: Recharts line chart showing historical actuals (blue), test-set predictions (green), and future forecast (orange dashed) with a vertical split line; chart footer shows real RMSE/MAE/MAPE sourced from the winning experiment
- **Forecast table**: next N forecasted values with generated dates and one-click CSV download
- **Timeseries-specific approval gate**: dedicated `TimeSeriesApprovalGate` component lets users confirm date column, target column, forecast horizon, and evaluation metric before the pipeline runs
- **Stationarity / trend / seasonality profiling**: ADF test, linear regression R², and autocorrelation at the seasonal lag displayed as stats tiles above the standard column profile
- **Time series endpoint**: generated `endpoint.py` exposes `GET /history`, `GET /forecast`, and `POST /predict (recent_values)` instead of the row-feature-based predict used by other services
- **Auto-detection extended**: `POST /auto/jobs` now detects and routes time series jobs based on datetime columns and forecasting intent
- **E2B executor extended**: captures `FORECAST:[...]` stdout marker alongside the existing `__MODEL_PKL__:` marker; stores `mae`, `mape`, date strings, and `feature_columns` from output JSON
- **Gateway updated**: all four services (ports 8001–8004) proxied through gateway with unified health check
- **Landing page**: 4-card grid**: new emerald Time Series card added; grid changed to `sm:grid-cols-2 lg:grid-cols-4`

**Air Passengers benchmark:** MAPE **6.4%** · RMSE **33.98** · MAE **28.79** 12-month forecast on classic 1949–1960 monthly passenger data; Experiment B (LGBM/XGB with lag features) outperformed Experiment A by 2× on RMSE.

### v3.0

- **Multi-class classification pipeline** full 10-agent pipeline supporting 3–20 categories; LabelEncoder target handling; per-class F1 stored in pkl; `all_probabilities` on every prediction
- **AI auto-detection (Quick Start)** `POST /auto/jobs` detects task type from data + description via LLM; routes to the correct pipeline; frontend shows detected type with reasoning and confidence before redirect
- **Runner-up model override** model selection screen redesigned as two interactive radio cards; click either experiment to select it before approving
- **Dataset interpretation cards** LLM bullet points rendered as styled, color-coded insight cards instead of raw text
- **Landing page scrollable** page now scrolls naturally; Quick Start panel visible below task cards
- **ApprovalGate extended** multiclass_classification task type option with appropriate metric choices
- **`?job=<id>` URL routing** all pipeline pages accept a pre-created job ID via query param, enabling post-auto-detect redirect

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

- **Tabular data only**: no image, text, or audio support
- **Multi-class range**: targets with more than 20 unique values trigger a warning; use regression or manual binning
- **Time series minimum length**: at least 50 rows required after lag/rolling feature creation (lags consume 14 rows)
- **Time series forecast drift**: recursive forecasting propagates errors; longer horizons (> 30 steps) become less reliable
- **E2B required**: experiments need an active E2B API key and internet access
- **Ollama must run locally**: LLM inference is not remote; Ollama must be on the same machine as the backend
- **Windows Celery**: requires `--pool=solo`; Linux/macOS can use the default `prefork` pool
- **sklearn version coupling**: `model.pkl` is built inside E2B; if loading locally fails, pin `scikit-learn>=1.3.0,<2.0.0`

---

## License

MIT
