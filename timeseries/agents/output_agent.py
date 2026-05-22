import base64
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from timeseries.state import TimeSeriesState as PrometheusState
from shared.llm.router import LLMRouter
from timeseries.config import ARTIFACTS_DIR

SYSTEM_PROMPT = """Generate a FastAPI Python script that serves a time series forecasting model.

The model is saved in model.pkl, a Python dict with keys:
- model: the trained sklearn/xgboost/lightgbm regressor
- feature_cols: list of feature column names
- date_col: the datetime column name
- target_col: the target column name
- train_actuals: list of training target values
- test_actuals: list of test target values
- test_predictions: list of test set predictions
- train_dates: list of training date strings
- test_dates: list of test date strings
- train_end_date: last training date string
- test_end_date: last test date string
- rmse, mae, mape: performance metrics

Target column: {target_column}
Date column: {date_column}
Frequency: {frequency}
Forecast horizon: {forecast_horizon}
Model type: {model_type}

Generate EXACTLY this structure — only Python code, no markdown, no backticks:

import pickle
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any
import numpy as np

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_model_data = None

@app.on_event("startup")
async def load_model():
    global _model_data
    with open("model.pkl", "rb") as f:
        _model_data = pickle.load(f)

@app.get("/forecast")
async def get_forecast():
    \"\"\"Returns the pre-computed forward forecast beyond the training dataset.\"\"\"
    # The forecast_values are stored in the main app (timeseries service) state
    # This endpoint is a placeholder — the timeseries service serves the actual forecast
    return {{"message": "Use the Prometheus timeseries service /forecast endpoint for live forecasts."}}

@app.get("/history")
async def get_history():
    \"\"\"Returns historical actuals and test-set predictions for visualization.\"\"\"
    try:
        return {{
            "train_dates": _model_data.get("train_dates", []),
            "train_actuals": _model_data.get("train_actuals", []),
            "test_dates": _model_data.get("test_dates", []),
            "test_actuals": _model_data.get("test_actuals", []),
            "test_predictions": _model_data.get("test_predictions", []),
            "split_date": _model_data.get("train_end_date", ""),
            "rmse": _model_data.get("rmse", 0),
            "mae": _model_data.get("mae", 0),
            "mape": _model_data.get("mape", 0),
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PredictInput(BaseModel):
    recent_values: List[float]  # last known target values, in chronological order

@app.post("/predict")
async def predict(input_data: PredictInput):
    \"\"\"Accepts the last N known values and returns the next step prediction.\"\"\"
    try:
        model = _model_data["model"]
        feature_cols = _model_data["feature_cols"]
        recent = input_data.recent_values

        # Build feature row from recent values (same logic as training)
        row = {{}}
        lags = {{1: 1, 2: 2, 3: 3, 7: 7, 14: 14}}
        for lag_name, lag_n in lags.items():
            col = f"lag_{{lag_name}}"
            if col in feature_cols:
                row[col] = recent[-lag_n] if len(recent) >= lag_n else recent[0]
        for col in feature_cols:
            if col not in row:
                row[col] = 0.0  # Date features default to 0

        feat = np.array([row.get(c, 0.0) for c in feature_cols]).reshape(1, -1)
        prediction = float(model.predict(feat)[0])

        return {{
            "prediction": round(prediction, 6),
            "model_type": "{model_type}",
            "target_column": "{target_column}",
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {{"status": "healthy", "model_type": "{model_type}", "task_type": "timeseries"}}

@app.get("/info")
async def info():
    return {{
        "target_column": "{target_column}",
        "date_column": "{date_column}",
        "frequency": "{frequency}",
        "forecast_horizon": {forecast_horizon},
        "rmse": _model_data.get("rmse", 0) if _model_data else 0,
        "mae": _model_data.get("mae", 0) if _model_data else 0,
        "mape": _model_data.get("mape", 0) if _model_data else 0,
    }}

Return ONLY valid Python code. No markdown fences. No text before or after the code."""

REQUIREMENTS = """fastapi>=0.110.0
uvicorn>=0.29.0
pydantic>=2.0.0
scikit-learn>=1.3.0
xgboost>=2.0.0
lightgbm>=4.0.0
pandas>=2.0.0
numpy>=1.26.0
"""


def _generate_forecast_dates(last_date: str, frequency: str, horizon: int) -> List[str]:
    """Generate future date strings beyond the last training date."""
    try:
        dt = datetime.strptime(last_date, "%Y-%m-%d")
        freq_map = {"hourly": timedelta(hours=1), "daily": timedelta(days=1),
                    "weekly": timedelta(weeks=1), "monthly": timedelta(days=30)}
        delta = freq_map.get(frequency, timedelta(days=1))
        return [str((dt + delta * (i + 1)).date()) for i in range(horizon)]
    except Exception:
        return [f"step_{i+1}" for i in range(horizon)]


def _extract_python_code(raw: str) -> str:
    raw = raw.strip()
    if "```python" in raw:
        start = raw.index("```python") + len("```python")
        end = raw.rfind("```", start)
        return raw[start:end].strip() if end > start else raw[start:].strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        return "\n".join(inner).strip()
    lines = raw.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(("import ", "from ", "class ", "def ", "@app", "#!")):
            return "\n".join(lines[i:]).strip()
    return raw


async def output_agent_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    winning = state["winning_experiment"]
    target_column = state.get("target_column", "")
    date_column = state.get("date_column", "")
    model_type = winning.get("architecture_name", "MLModel")
    frequency = state.get("frequency", "daily")
    forecast_horizon = state.get("forecast_horizon", 30)

    system_prompt = SYSTEM_PROMPT.format(
        target_column=target_column,
        date_column=date_column,
        frequency=frequency,
        forecast_horizon=forecast_horizon,
        model_type=model_type,
    )

    endpoint_code = None
    for attempt in range(2):
        raw = await router.call(
            task_type="code_generation",
            system_prompt=system_prompt,
            user_message="Generate the FastAPI endpoint Python file now. Return ONLY Python code — no markdown, no prose.",
        )
        raw = _extract_python_code(raw)

        is_valid = "history" in raw and "FastAPI" in raw and "model.pkl" in raw
        if is_valid:
            endpoint_code = raw
            break
        elif attempt == 0:
            system_prompt = (
                "The previous response was not clean Python. Return ONLY the Python source code "
                "for a FastAPI app that loads model.pkl and exposes GET /history and POST /predict. "
                "No markdown, no backticks, no text before or after the code."
            )

    if endpoint_code is None:
        endpoint_code = "# Code generation failed — please regenerate manually."

    state["generated_endpoint_code"] = endpoint_code
    state["generated_requirements"] = REQUIREMENTS

    # Generate forecast dates
    last_date = state.get("test_cutoff_date") or winning.get("parsed_metrics", {}).get("test_end_date", "")
    if last_date:
        state["forecast_dates"] = _generate_forecast_dates(last_date, frequency, forecast_horizon)

    # Save winning model pickle
    winning = state.get("winning_experiment") or {}
    pkl_b64 = winning.get("model_pkl_b64")
    if pkl_b64:
        try:
            pkl_path = os.path.join(ARTIFACTS_DIR, f"{state['job_id']}_model.pkl")
            with open(pkl_path, "wb") as f:
                f.write(base64.b64decode(pkl_b64))
            state["model_pkl_path"] = pkl_path
        except Exception:
            state["model_pkl_path"] = None
    else:
        state["model_pkl_path"] = None

    state["current_phase"] = "complete"

    state["debug_log"].append({
        "phase": "output_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoint_code_length": len(endpoint_code),
        "forecast_dates_generated": len(state.get("forecast_dates") or []),
    })

    return state
