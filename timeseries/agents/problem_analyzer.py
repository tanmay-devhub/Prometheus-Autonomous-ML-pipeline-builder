import json
from datetime import datetime
from typing import Any, Dict

import pandas as pd
import numpy as np

from timeseries.state import TimeSeriesState as PrometheusState
from shared.llm.router import LLMRouter
from timeseries.config import ALLOWED_TASK_TYPES, ALLOWED_METRICS

SYSTEM_PROMPT = """You are an expert ML engineer analyzing a time series forecasting problem.
You will be given:
1. A plain English description of what the user wants to predict
2. The column names of their dataset
3. Five sample rows of their dataset

Your job is to return a JSON object with exactly these fields:
{
  "task_type": "timeseries",
  "date_column": "<exact column name that contains dates/timestamps>",
  "target_column": "<exact column name to forecast>",
  "evaluation_metric": "rmse",
  "frequency": "daily" | "weekly" | "monthly" | "hourly",
  "forecast_horizon": <int, default 30>,
  "confidence": 0.0-1.0,
  "reasoning": "<one sentence explaining why this is a time series problem>",
  "domain_flags": ["<any domain flags>"],
  "warnings": ["<any concerns>"]
}

Rules:
- task_type MUST always be "timeseries" — this service only handles time series forecasting
- date_column MUST contain dates, timestamps, months, or sequential time periods
- target_column MUST be numeric and represent the quantity to forecast over time
- evaluation_metric should be "rmse" by default
- frequency: detect from column names or sample data ("Month" → monthly, "Date" → daily, etc.)
- forecast_horizon: use the user's stated horizon or default to 30
- Only return valid JSON. No markdown, no explanation, no backticks."""

CORRECTIVE_JSON_PROMPT = "Your previous response was not valid JSON. Return only the JSON object, nothing else."
CORRECTIVE_COLUMN_PROMPT = (
    "The column you returned does not exist in the dataset. "
    "You must choose from exactly these column names: {columns}. "
    "Return only the corrected JSON object."
)


def _detect_frequency(df: pd.DataFrame, date_col: str) -> str:
    """Detect time series frequency from median time delta."""
    try:
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna().sort_values()
        if len(dates) < 2:
            return "daily"
        deltas = dates.diff().dropna()
        median_hours = deltas.median().total_seconds() / 3600
        if median_hours < 2:
            return "hourly"
        elif median_hours < 48:
            return "daily"
        elif median_hours < 240:
            return "weekly"
        else:
            return "monthly"
    except Exception:
        return "daily"


async def problem_analyzer_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    columns = state["dataset_columns"]
    sample_rows = state["dataset_sample_rows"]

    user_message = (
        f"User description: {state['user_description']}\n\n"
        f"Dataset columns: {columns}\n\n"
        f"Sample rows (first 5):\n{json.dumps(sample_rows, indent=2)}"
    )

    parsed = None
    retries = 0
    current_user_message = user_message

    for attempt in range(3):
        raw = await router.call(
            task_type="analysis",
            system_prompt=SYSTEM_PROMPT,
            user_message=current_user_message,
        )

        try:
            parsed = json.loads(raw.strip())
        except json.JSONDecodeError:
            retries += 1
            current_user_message = CORRECTIVE_JSON_PROMPT
            continue

        if parsed.get("date_column") not in columns:
            retries += 1
            current_user_message = CORRECTIVE_COLUMN_PROMPT.format(columns=columns)
            parsed = None
            continue

        if parsed.get("target_column") not in columns:
            retries += 1
            current_user_message = CORRECTIVE_COLUMN_PROMPT.format(columns=columns)
            parsed = None
            continue

        if parsed.get("task_type") != "timeseries":
            parsed["task_type"] = "timeseries"

        break

    if parsed is None:
        state["error_message"] = "Problem analyzer failed to return valid analysis after 3 retries."
        state["current_phase"] = "failed"
        return state

    # Auto-detect frequency from actual data if LLM frequency seems off
    try:
        df = pd.read_csv(state["dataset_path"])
        detected_freq = _detect_frequency(df, parsed.get("date_column", ""))
        if detected_freq and not parsed.get("frequency"):
            parsed["frequency"] = detected_freq
    except Exception:
        pass

    state["task_type"] = "timeseries"
    state["date_column"] = parsed.get("date_column")
    state["target_column"] = parsed.get("target_column")
    state["evaluation_metric"] = parsed.get("evaluation_metric", "rmse")
    state["frequency"] = parsed.get("frequency", "daily")
    state["forecast_horizon"] = int(parsed.get("forecast_horizon", 30))
    state["domain_flags"] = parsed.get("domain_flags", [])
    state["problem_analysis_raw"] = json.dumps(parsed)

    state["debug_log"].append({
        "phase": "problem_analyzer",
        "timestamp": datetime.utcnow().isoformat(),
        "output": parsed,
        "retries_used": retries,
    })

    state["current_phase"] = "awaiting_problem_approval"
    return state
