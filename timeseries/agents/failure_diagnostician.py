import json
from typing import Any, Dict

from timeseries.state import TimeSeriesState as PrometheusState, ExperimentResult
from shared.llm.router import LLMRouter

FIX_STRATEGIES = {
    "syntax_error": (
        "The generated code has a Python syntax error. Rewrite the entire script from scratch. Error: {error_message}"
    ),
    "import_error": (
        "The code imports a library that is not available. Remove all imports except: "
        "pandas, numpy, sklearn, xgboost, lightgbm, scipy, json, sys, os, re, warnings. "
        "Error: {error_message}"
    ),
    "date_parse_error": (
        "The date column '{date_column}' cannot be parsed as dates. "
        "Add error handling: df['{date_column}'] = pd.to_datetime(df['{date_column}'], errors='coerce', infer_datetime_format=True). "
        "Then drop rows where date is NaT."
    ),
    "column_error": (
        "The code references a column that does not exist. The exact column names available are: "
        "{column_list}. Rewrite all DataFrame column references to use only these exact column names."
    ),
    "type_error": (
        "A type error occurred. Ensure all numeric columns are converted with pd.to_numeric(errors='coerce'). "
        "Error: {error_message}"
    ),
    "insufficient_data": (
        "After creating lag features and dropping NaN rows, there is not enough data left. "
        "Reduce the maximum lag from 14 to 7. Use shorter rolling windows (3 instead of 7). "
        "Ensure at least 20 rows remain after dropna()."
    ),
    "feature_name_error": (
        "XGBoost/LightGBM requires feature names without special characters. "
        "Sanitize column names: df.columns = [re.sub(r'[^A-Za-z0-9_]', '_', c) for c in df.columns]."
    ),
    "convergence_failure": (
        "The model did not converge. For LinearRegression or Ridge, this is unusual — "
        "switch to Ridge(alpha=1.0) which is more numerically stable."
    ),
    "output_parse_error": (
        "The script did not print valid JSON on the last non-FORECAST line. "
        "Ensure the very last print statement (after the FORECAST: line) outputs exactly:\n"
        "print(json.dumps({'metric_name': 'rmse', 'metric_value': <float>, "
        "'mae': <float>, 'mape': <float>, 'model_type': '<name>', "
        "'train_samples': <int>, 'test_samples': <int>, "
        "'forecast_horizon': <int>, 'train_start_date': '<str>', 'train_end_date': '<str>', "
        "'test_start_date': '<str>', 'test_end_date': '<str>', 'feature_columns': [<list>]}))"
    ),
    "poor_metric": (
        "The model performance is poor (MAPE > 30%). Try: "
        "(1) Add more lag features (t-21, t-28 for weekly patterns), "
        "(2) Add sin/cos encoding of month for seasonality, "
        "(3) Switch to XGBRegressor or LGBMRegressor for more expressive power."
    ),
    "memory_error": (
        "The model ran out of memory. Switch to LinearRegression or Ridge, "
        "or reduce n_estimators to 50 for tree models."
    ),
    "timeout_error": (
        "Execution timed out. Use LinearRegression or Ridge (fastest), "
        "or reduce n_estimators to 30 for tree models."
    ),
    "forecast_error": (
        "The forward forecast generation failed. Simplify the recursive forecast loop: "
        "only shift lag_1 = pred each step and leave other features constant."
    ),
}

FAILURE_TAXONOMY = [
    "syntax_error", "import_error", "date_parse_error", "column_error", "type_error",
    "insufficient_data", "feature_name_error", "convergence_failure",
    "memory_error", "timeout_error", "output_parse_error", "poor_metric", "forecast_error",
]


def _rule_based_classify(experiment_result: ExperimentResult, state: PrometheusState) -> str | None:
    error_type = experiment_result.get("error_type") or ""
    stderr = (experiment_result.get("stderr") or "") + (experiment_result.get("stdout") or "")
    failure_type = experiment_result.get("failure_type")

    if error_type == "TimeoutError":
        return "timeout_error"
    if error_type == "OutputParseError":
        return "output_parse_error"
    if "MemoryError" in stderr:
        return "memory_error"
    if "ImportError" in stderr or "ModuleNotFoundError" in stderr:
        return "import_error"
    if "SyntaxError" in stderr:
        return "syntax_error"
    if "ParserError" in stderr or ("to_datetime" in stderr and "Error" in stderr):
        return "date_parse_error"
    if "Not enough data" in stderr or "ValueError" in stderr and "split" in stderr:
        return "insufficient_data"
    if "feature_names may not contain" in stderr or (
        "ValueError" in stderr and any(c in stderr for c in ["<", "[", "]"])
    ):
        return "feature_name_error"
    if "KeyError" in stderr:
        return "column_error"
    if "TypeError" in stderr:
        return "type_error"
    if "FORECAST" in stderr and "Error" in stderr:
        return "forecast_error"
    if failure_type in FAILURE_TAXONOMY:
        return failure_type
    return None


async def failure_diagnostician_node(
    state: PrometheusState, experiment_result: ExperimentResult
) -> Dict[str, str]:
    failure_type = _rule_based_classify(experiment_result, state)

    if not failure_type:
        router = LLMRouter()
        raw = await router.call(
            task_type="analysis",
            system_prompt=(
                "You are an ML debugging expert for time series forecasting scripts. "
                "Classify the failure into exactly one of these types: "
                + ", ".join(FAILURE_TAXONOMY)
            ),
            user_message=(
                f"STDOUT:\n{experiment_result.get('stdout', '')[:2000]}\n\n"
                f"STDERR:\n{experiment_result.get('stderr', '')[:2000]}\n\n"
                f"Return JSON: {{\"failure_type\": \"<one of the taxonomy values>\"}}"
            ),
        )
        try:
            parsed = json.loads(raw.strip())
            failure_type = parsed.get("failure_type", "output_parse_error")
        except json.JSONDecodeError:
            failure_type = "output_parse_error"

    template = FIX_STRATEGIES.get(failure_type, FIX_STRATEGIES["output_parse_error"])
    fix_instructions = template.format(
        error_message=experiment_result.get("error_message", ""),
        column_list=state["dataset_columns"],
        date_column=state.get("date_column", ""),
        task_type="timeseries",
        metric_name="rmse",
    )

    return {
        "failure_type": failure_type,
        "fix_strategy": failure_type,
        "fix_instructions": fix_instructions,
    }
