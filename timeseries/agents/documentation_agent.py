import json
import os
from datetime import datetime
from typing import Any, Dict

from timeseries.state import TimeSeriesState as PrometheusState
from shared.llm.router import LLMRouter
from shared.execution.e2b_executor import E2BExecutor

MODEL_CARD_PROMPT = """Generate a model card for this time series forecasting model. Use this exact markdown structure:

# Model Card: {model_type}

## Model Details
- **Task:** Time Series Forecasting
- **Algorithm:** {model_type}
- **Date column:** {date_column}
- **Target variable:** {target_column}
- **Forecast horizon:** {forecast_horizon} steps ahead
- **Frequency:** {frequency}
- **Primary metric (RMSE):** {rmse}
- **MAE:** {mae}
- **MAPE:** {mape}% (on average, predictions are {mape}% from actual values)
- **Training period:** {train_start_date} to {train_end_date}
- **Test period:** {test_start_date} to {test_end_date}

## Training Data
[Describe the dataset characteristics based on this profile: {profile_summary}]

## Performance
[Interpret the MAPE value in plain English — e.g. "On average, the model's predictions are X% away from actual values." Is this good, acceptable, or poor for this domain?]

## Limitations
[List 3-5 specific limitations based on whether the series has trend/seasonality, the test period length, and the model type]

## Intended Use
[Describe appropriate use cases for this model based on the problem description: {user_description}]

## How Not To Use
[List 2-3 situations where this model should not be trusted for forecasting]"""

SHAP_SCRIPT_TEMPLATE = """
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import json
import sys

try:
    import shap

    DATE_COL = {date_col_repr}
    TARGET_COL = {target_col_repr}

    df = pd.read_csv(sys.argv[1])
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    df = df.sort_values(DATE_COL).reset_index(drop=True)

    for lag in [1, 2, 3, 7, 14]:
        df[f'lag_{{lag}}'] = df[TARGET_COL].shift(lag)
    df['rolling_mean_7'] = df[TARGET_COL].rolling(7).mean()
    df['rolling_mean_30'] = df[TARGET_COL].rolling(30).mean()
    df['rolling_std_7'] = df[TARGET_COL].rolling(7).std()
    df['day_of_week'] = df[DATE_COL].dt.dayofweek
    df['month'] = df[DATE_COL].dt.month
    df['quarter'] = df[DATE_COL].dt.quarter
    df['day_of_year'] = df[DATE_COL].dt.dayofyear
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    df = df.dropna()

    feature_cols = [c for c in df.columns if c not in [DATE_COL, TARGET_COL]]
    X = df[feature_cols]
    y = df[TARGET_COL]

    from sklearn.ensemble import GradientBoostingRegressor
    from xgboost import XGBRegressor
    from lightgbm import LGBMRegressor

    model_class = {model_class_repr}
    try:
        model = model_class()
        model.fit(X, y)
    except Exception:
        model = GradientBoostingRegressor(n_estimators=50)
        model.fit(X, y)

    try:
        explainer = shap.TreeExplainer(model)
    except Exception:
        explainer = shap.LinearExplainer(model, X)

    shap_values = explainer.shap_values(X[:100])
    if isinstance(shap_values, list):
        shap_values = shap_values[0]

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    top_indices = np.argsort(mean_abs_shap)[::-1][:10]
    top_features = [
        {{"feature": feature_cols[i], "importance": float(mean_abs_shap[i])}}
        for i in top_indices
    ]
    print(json.dumps(top_features))
except Exception as e:
    print(json.dumps([{{"error": str(e)}}]))
"""


async def documentation_agent_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    winning = state["winning_experiment"]
    profile = state.get("profile_report", {})
    metrics = winning.get("parsed_metrics", {})
    model_type = winning.get("architecture_name", "ML Model")

    rmse = round(metrics.get("rmse", metrics.get("metric_value", 0.0)), 4)
    mae = round(metrics.get("mae", 0.0), 4)
    mape = round(metrics.get("mape", 0.0), 2)

    profile_summary = json.dumps({
        "row_count": profile.get("row_count"),
        "date_range": profile.get("time_span", {}),
        "is_stationary": profile.get("is_stationary"),
        "has_trend": profile.get("has_trend"),
        "has_seasonality": profile.get("has_seasonality"),
        "warnings": [w["message"] for w in state.get("validation_warnings", [])[:5]],
        "llm_insights": profile.get("llm_interpretation", ""),
    })

    card_prompt = MODEL_CARD_PROMPT.format(
        model_type=model_type,
        date_column=state.get("date_column", ""),
        target_column=state.get("target_column", ""),
        forecast_horizon=state.get("forecast_horizon", 30),
        frequency=state.get("frequency", "daily"),
        rmse=rmse,
        mae=mae,
        mape=mape,
        train_start_date=metrics.get("train_start_date", "N/A"),
        train_end_date=metrics.get("train_end_date", "N/A"),
        test_start_date=metrics.get("test_start_date", "N/A"),
        test_end_date=metrics.get("test_end_date", "N/A"),
        profile_summary=profile_summary,
        user_description=state["user_description"],
    )

    model_card = await router.call(
        task_type="interpretation",
        system_prompt="You are an ML documentation expert writing a model card for a time series forecasting model.",
        user_message=card_prompt,
    )

    # SHAP feature importance
    shap_script = SHAP_SCRIPT_TEMPLATE.format(
        date_col_repr=repr(state.get("date_column", "")),
        target_col_repr=repr(state.get("target_column", "")),
        model_class_repr=model_type,
    )

    executor = E2BExecutor()
    shap_result = await executor.run(
        code=shap_script,
        dataset_path=state["dataset_path"],
    )

    shap_features = []
    plain_explanation = ""
    if shap_result.success:
        try:
            stdout_lines = [l.strip() for l in shap_result.stdout.strip().split("\n") if l.strip()]
            # Skip FORECAST lines
            json_lines = [l for l in stdout_lines if not l.startswith("FORECAST:") and not l.startswith("__MODEL_PKL__:")]
            if json_lines:
                shap_features = json.loads(json_lines[-1])

            shap_prompt = (
                f"These are the top features driving this time series forecasting model:\n"
                f"{json.dumps(shap_features, indent=2)}\n\n"
                f"The model forecasts {state.get('target_column', 'the target')} "
                f"{state.get('forecast_horizon', 30)} steps ahead.\n"
                f"In plain English, explain what drives the forecasts for a non-technical stakeholder.\n"
                f"Reference the actual feature names (lag_1 = yesterday's value, month = calendar month, etc.).\n"
                f"Keep it under 150 words. Use simple language."
            )
            plain_explanation = await router.call(
                task_type="interpretation",
                system_prompt="You are an expert at explaining time series ML models to non-technical stakeholders.",
                user_message=shap_prompt,
            )
        except Exception:
            plain_explanation = (
                f"The model achieved MAPE = {mape}% on the test set, meaning predictions are on average "
                f"{mape:.1f}% away from actual values."
            )

    state["model_card"] = model_card
    state["plain_english_explanation"] = plain_explanation
    state["shap_plot_path"] = None
    state["profile_report"]["shap_features"] = shap_features

    state["debug_log"].append({
        "phase": "documentation_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "model_card_length": len(model_card),
        "shap_features_count": len(shap_features),
    })

    return state
