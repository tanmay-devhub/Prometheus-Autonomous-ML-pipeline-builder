import json
from datetime import datetime
from typing import Any, Dict, List

from timeseries.state import TimeSeriesState as PrometheusState
from shared.llm.router import LLMRouter
from timeseries.config import ALLOWED_MODEL_TYPES

SYSTEM_PROMPT = """You are an expert ML engineer designing time series forecasting pipelines.
You will receive a data profile and must propose exactly 2 different pipeline architectures.

CRITICAL RULES:
- Time series CANNOT use random train/test splits. Always use chronological split (first 80% = train, last 20% = test).
- Never suggest: classifiers, LogisticRegression, any classification model.
- Only these models are allowed: XGBRegressor, LGBMRegressor, RandomForestRegressor, LinearRegression, Ridge.
- Feature engineering is MANDATORY (lag features, rolling features, date features).
- Always mention whether you handle non-stationarity (differencing) or seasonality encoding.

The architectures must be meaningfully different:
- A gradient boosting model vs a linear/simpler model
- One that handles seasonality explicitly vs one that relies on lag features alone

For each architecture, return a JSON object with exactly these fields:
{
  "name": "<short descriptive name, e.g. 'xgb_lag_features'>",
  "model_type": "<exact sklearn/xgboost/lightgbm class name>",
  "hyperparameters": {"<param>": <value>},
  "handles_seasonality": true|false,
  "seasonality_strategy": "<none|sin_cos_encoding|lag_features>",
  "handles_trend": true|false,
  "trend_strategy": "<none|time_index_feature|differencing>",
  "justification": "<2 sentences explaining why this architecture fits this specific dataset>",
  "expected_strength": "<what this model is good at>",
  "expected_weakness": "<what this model struggles with>"
}

Return a JSON array of exactly 2 architecture objects.
Only return valid JSON. No markdown, no backticks, no explanation.

Allowed model types ONLY:
- XGBRegressor
- LGBMRegressor
- RandomForestRegressor
- LinearRegression
- Ridge"""


async def pipeline_designer_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    profile = state.get("profile_report", {})
    date_col = state.get("date_column")
    target_col = state.get("target_column")
    frequency = state.get("frequency", "daily")
    forecast_horizon = state.get("forecast_horizon", 30)
    is_stationary = state.get("is_stationary", True)
    has_trend = state.get("has_trend", False)
    has_seasonality = state.get("has_seasonality", False)

    col_stats = profile.get("columns", [])
    null_rates = {c["column"]: c["null_pct"] for c in col_stats}

    user_message = (
        f"Task type: timeseries\n"
        f"Date column: {date_col}\n"
        f"Target column: {target_col}\n"
        f"Evaluation metric: {state['evaluation_metric']}\n"
        f"Frequency: {frequency}\n"
        f"Forecast horizon: {forecast_horizon} steps\n"
        f"Row count: {profile.get('row_count', 'unknown')}\n"
        f"Is stationary: {is_stationary} (ADF p-value: {profile.get('adf_p_value', 'N/A')})\n"
        f"Has trend: {has_trend} (R²: {profile.get('trend_r2', 'N/A')})\n"
        f"Has seasonality: {has_seasonality} (autocorr: {profile.get('seasonality_autocorr', 'N/A')})\n"
        f"Validation warnings: {json.dumps(state['validation_warnings'])}\n"
        f"LLM insights:\n{profile.get('llm_interpretation', '')}"
    )

    architectures = None
    retries = 0
    current_message = user_message

    for attempt in range(3):
        raw = await router.call(
            task_type="reasoning",
            system_prompt=SYSTEM_PROMPT,
            user_message=current_message,
        )

        try:
            parsed = json.loads(raw.strip())
        except json.JSONDecodeError:
            retries += 1
            current_message = "Your previous response was not valid JSON. Return only the JSON array of 2 architectures."
            continue

        if not isinstance(parsed, list) or len(parsed) != 2:
            retries += 1
            current_message = "You must return a JSON array of exactly 2 architecture objects. Try again."
            continue

        invalid_models = [
            a.get("model_type") for a in parsed
            if a.get("model_type") not in ALLOWED_MODEL_TYPES
        ]
        if invalid_models:
            retries += 1
            current_message = (
                f"model_type values {invalid_models} are not in the allowed list. "
                f"Allowed: {sorted(ALLOWED_MODEL_TYPES)}. Return corrected JSON array only."
            )
            continue

        architectures = parsed
        break

    if architectures is None:
        state["error_message"] = "Pipeline designer failed to produce valid architectures after 3 retries."
        state["current_phase"] = "failed"
        return state

    state["architectures"] = architectures
    state["current_phase"] = "design_complete"
    state["debug_log"].append({
        "phase": "pipeline_designer",
        "timestamp": datetime.utcnow().isoformat(),
        "architectures": [a["name"] for a in architectures],
        "retries_used": retries,
    })

    return state
