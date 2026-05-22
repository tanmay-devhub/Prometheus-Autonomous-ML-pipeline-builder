import json
import textwrap
from typing import Dict

from timeseries.state import TimeSeriesState as PrometheusState
from shared.llm.router import LLMRouter

SCRIPT_TEMPLATE = """\
import warnings
warnings.filterwarnings('ignore')
import sys
import json
import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_error
{extra_imports}

try:
    DATE_COL = '{date_column}'
    TARGET_COL = '{target_column}'
    FORECAST_HORIZON = {forecast_horizon}

    df = pd.read_csv(sys.argv[1])
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    df = df.sort_values(DATE_COL).reset_index(drop=True)

    # Lag features
    for lag in [1, 2, 3, 7, 14]:
        df[f'lag_{{lag}}'] = df[TARGET_COL].shift(lag)

    # Rolling features
    df['rolling_mean_7'] = df[TARGET_COL].rolling(7).mean()
    df['rolling_mean_30'] = df[TARGET_COL].rolling(30).mean()
    df['rolling_std_7'] = df[TARGET_COL].rolling(7).std()

    # Date features
    df['day_of_week'] = df[DATE_COL].dt.dayofweek
    df['month'] = df[DATE_COL].dt.month
    df['quarter'] = df[DATE_COL].dt.quarter
    df['day_of_year'] = df[DATE_COL].dt.dayofyear
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

    df = df.dropna()
    if len(df) < 10:
        raise ValueError("Not enough data after creating lag features")

    feature_cols = [c for c in df.columns if c not in [DATE_COL, TARGET_COL]]

    # Chronological split — NEVER random
    split_idx = int(len(df) * 0.8)
    train = df.iloc[:split_idx]
    test = df.iloc[split_idx:]

    if len(train) < 5 or len(test) < 2:
        raise ValueError(f"Not enough data after split: train={{len(train)}}, test={{len(test)}}")

    X_train = train[feature_cols].values
    y_train = train[TARGET_COL].values
    X_test = test[feature_cols].values
    y_test = test[TARGET_COL].values

    train_start_date = str(train[DATE_COL].iloc[0].date())
    train_end_date = str(train[DATE_COL].iloc[-1].date())
    test_start_date = str(test[DATE_COL].iloc[0].date())
    test_end_date = str(test[DATE_COL].iloc[-1].date())

    # --- model block ---
{model_block}
    # --- end model block ---

    model.fit(X_train, y_train)

    # Save model pickle
    try:
        import pickle as _pkl, base64 as _b64
        y_pred_for_save = model.predict(X_test).tolist()
        _save = {{
            'model': model,
            'feature_cols': feature_cols,
            'date_col': DATE_COL,
            'target_col': TARGET_COL,
            'train_actuals': y_train.tolist(),
            'test_actuals': y_test.tolist(),
            'test_predictions': y_pred_for_save,
            'train_dates': [str(d.date()) for d in train[DATE_COL]],
            'test_dates': [str(d.date()) for d in test[DATE_COL]],
            'train_end_date': train_end_date,
            'test_end_date': test_end_date,
        }}
        print(f"__MODEL_PKL__:{{_b64.b64encode(_pkl.dumps(_save)).decode('ascii')}}", flush=True)
    except Exception as _pkl_err:
        pass

    y_pred = model.predict(X_test)

    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    nonzero_mask = y_test != 0
    if nonzero_mask.sum() > 0:
        mape = float(np.mean(np.abs((y_test[nonzero_mask] - y_pred[nonzero_mask]) / y_test[nonzero_mask])) * 100)
    else:
        mape = 0.0

    # Forward forecast — recursive, FORECAST_HORIZON steps beyond the dataset
    last_row = df[feature_cols].iloc[-1].copy()
    forecast = []
    for step in range(FORECAST_HORIZON):
        pred = float(model.predict(last_row.values.reshape(1, -1))[0])
        forecast.append(round(pred, 6))
        # Shift lag features forward
        for lag in [14, 7, 3, 2]:
            prev_lag_col = f'lag_{{lag}}'
            next_lag_col = f'lag_{{lag - 1}}'
            if prev_lag_col in last_row.index and next_lag_col in last_row.index:
                last_row[prev_lag_col] = last_row[next_lag_col]
        if 'lag_1' in last_row.index:
            last_row['lag_1'] = pred
        if 'rolling_mean_7' in last_row.index:
            last_row['rolling_mean_7'] = (last_row['rolling_mean_7'] * 6 + pred) / 7

    print("FORECAST:" + json.dumps(forecast), flush=True)

    print(json.dumps({{
        "metric_name": "rmse",
        "metric_value": round(rmse, 6),
        "mae": round(mae, 6),
        "mape": round(mape, 4),
        "model_type": "{model_type}",
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "forecast_horizon": FORECAST_HORIZON,
        "train_start_date": train_start_date,
        "train_end_date": train_end_date,
        "test_start_date": test_start_date,
        "test_end_date": test_end_date,
        "feature_columns": feature_cols,
    }}))

except Exception as e:
    print(json.dumps({{"error": True, "error_type": type(e).__name__, "error_message": str(e)}}))
"""

FALLBACK_BLOCK = (
    "    from sklearn.ensemble import RandomForestRegressor\n"
    "    model = RandomForestRegressor(n_estimators=100, random_state=42)"
)

MODEL_BLOCK_PROMPT = """Write ONLY the model instantiation block for a Python time series ML script.

Architecture spec:
{arch_json}

Context:
- Task type: timeseries (forecasting)
- X_train, X_test are already prepared (all numeric, no NaN) — lag features, rolling features, date features
- The script calls model.fit(X_train, y_train) automatically after your block

Your block must:
1. Import the model class
2. Instantiate the model with the hyperparameters from the spec

Hard rules:
- Every line MUST begin with exactly 4 spaces
- Variable MUST be named exactly: model
- Only import from: sklearn, xgboost, lightgbm
- ONLY use regression models: XGBRegressor, LGBMRegressor, RandomForestRegressor, LinearRegression, Ridge
- Do NOT use any classifier class (XGBClassifier, RandomForestClassifier, etc.)
- Do NOT call model.fit() — handled by the script
- Return ONLY the indented block — no markdown, no backticks, no explanation"""


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return raw


def _normalize_block(block: str) -> str:
    lines = textwrap.dedent(block).split("\n")
    return "\n".join("    " + ln if ln.strip() else "" for ln in lines)


def _validate_block(block: str) -> tuple[bool, str]:
    dedented = textwrap.dedent(block)
    try:
        compile(dedented, "<model_block>", "exec")
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    if "model" not in block:
        return False, "Block must assign a variable named 'model'"
    # Reject classifier imports
    for bad in ("Classifier", "LogisticRegression"):
        if bad in block:
            return False, f"Time series must use regressor models, not '{bad}'"
    return True, ""


_MODEL_SENTINEL = "__PROMETHEUS_TS_MODEL_BLOCK__"


def _build_script(model_block, date_column, target_column, forecast_horizon, model_type, extra_imports=""):
    template_with_sentinel = SCRIPT_TEMPLATE.replace("{model_block}", _MODEL_SENTINEL)
    formatted = template_with_sentinel.format(
        extra_imports=extra_imports,
        date_column=date_column,
        target_column=target_column,
        forecast_horizon=forecast_horizon,
        model_type=model_type,
    )
    return formatted.replace(_MODEL_SENTINEL, _normalize_block(model_block))


async def code_generator_node(state: PrometheusState, architecture: Dict) -> str:
    router = LLMRouter()
    date_column = state["date_column"]
    target_column = state["target_column"]
    forecast_horizon = state.get("forecast_horizon", 30)
    model_type = architecture.get("model_type", "RandomForestRegressor")

    prompt = MODEL_BLOCK_PROMPT.format(
        arch_json=json.dumps(architecture, indent=2),
    )

    model_block = None
    for attempt in range(3):
        raw = await router.call(
            task_type="code_generation",
            system_prompt=(
                "You are an expert Python ML engineer specializing in time series forecasting. "
                "Output only indented Python code (4-space indent). No markdown, no prose."
            ),
            user_message=prompt,
        )
        raw = _strip_fences(raw)
        ok, err = _validate_block(raw)
        if ok:
            model_block = raw
            break
        prompt = (
            f"Issue: {err}\n\nFix it. 4-space indent, variable named 'model', regression model only.\n"
            f"Architecture: {json.dumps(architecture, indent=2)}\nReturn ONLY the block."
        )

    if model_block is None:
        model_block = FALLBACK_BLOCK

    extra_imports = ""
    if "XGB" in model_type:
        extra_imports = "from xgboost import XGBRegressor"
    elif "LGBM" in model_type:
        extra_imports = "from lightgbm import LGBMRegressor"

    return _build_script(
        model_block=model_block,
        date_column=date_column,
        target_column=target_column,
        forecast_horizon=forecast_horizon,
        model_type=model_type,
        extra_imports=extra_imports,
    )
