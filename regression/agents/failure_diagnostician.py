import json
from typing import Any, Dict

from regression.state import RegressionState, ExperimentResult
from shared.llm.router import LLMRouter

FIX_STRATEGIES = {
    "syntax_error": (
        "The generated code has a Python syntax error. Rewrite the entire script from scratch. "
        "Error: {error_message}"
    ),
    "import_error": (
        "The code imports a library that is not available. Remove all imports except: "
        "pandas, numpy, sklearn, xgboost, lightgbm, scipy, json, sys, os, re, warnings. "
        "Error: {error_message}"
    ),
    "column_error": (
        "The code references a column that does not exist. The exact column names available are: "
        "{column_list}. Rewrite all DataFrame column references to use only these exact column names."
    ),
    "type_error": (
        "The preprocessing fails due to a type mismatch. Add explicit type checking and conversion "
        "before each preprocessing step. Use pd.to_numeric(errors='coerce') for numeric columns. "
        "Error: {error_message}"
    ),
    "metric_model_mismatch": (
        "The metric is incompatible with the model type. "
        "Task: regression. Required metric: {metric_name}. "
        "For regression (Ridge, Lasso, RandomForest/GradientBoosting/XGB/LGBMRegressor): "
        "use mean_absolute_error, r2_score, or mean_squared_error — NEVER predict_proba. "
        "Fix the metric line: metric_value = mean_absolute_error(y_test_orig, y_pred_orig)"
    ),
    "convergence_failure": (
        "The model did not converge. Increase max_iter to 10000, add feature scaling."
    ),
    "memory_error": (
        "The model ran out of memory. Use a simpler model with fewer parameters, "
        "or sample 50% of training data."
    ),
    "timeout_error": (
        "Execution timed out. Use a faster model (Ridge or LGBMRegressor), "
        "reduce n_estimators to 50 if using tree models."
    ),
    "output_parse_error": (
        "The script did not print valid JSON on the last line. "
        "Task type: regression. Evaluation metric: {metric_name}. "
        "Ensure the very last print statement outputs exactly this structure:\n"
        "print(json.dumps({{'metric_name': '{metric_name}', 'metric_value': <float>, "
        "'mae': <float>, 'r2': <float>, 'rmse': <float>, "
        "'model_type': '<name>', 'train_samples': <int>, 'test_samples': <int>, "
        "'target_log_transformed': <bool>}}))\n"
        "Do NOT include 'encoding_map' or any other large objects in this final JSON line."
    ),
    "poor_metric": (
        "The regression model performance is poor. Try: (1) feature scaling with StandardScaler, "
        "(2) different imputation for missing values, (3) remove high-cardinality ID columns, "
        "(4) check if the target column needs a log transform (np.log1p)."
    ),
    "suspicious_metric": (
        "The metric is suspiciously perfect, suggesting data leakage. Review all features and remove "
        "any that are too correlated with the target. Leakage warnings: {leakage_warnings}"
    ),
    "feature_name_error": (
        "XGBoost/LightGBM requires feature names without special characters. "
        "After any pd.get_dummies() call, sanitize: "
        "df.columns = [re.sub(r'[^A-Za-z0-9_]', '_', c) for c in df.columns]. "
        "Apply to both train and test DataFrames."
    ),
}

FAILURE_TAXONOMY = [
    "syntax_error", "import_error", "column_error", "type_error",
    "metric_model_mismatch", "feature_name_error",
    "convergence_failure", "memory_error", "timeout_error",
    "output_parse_error", "poor_metric", "suspicious_metric",
]


def _rule_based_classify(experiment_result: ExperimentResult, state: RegressionState) -> str | None:
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
    if "predict_proba" in stderr and ("AttributeError" in stderr or "has no attribute" in stderr):
        return "metric_model_mismatch"
    if "feature_names may not contain" in stderr or (
        ("ValueError" in stderr or "InvalidParameterError" in stderr)
        and any(c in stderr for c in ["<", "[", "]", " "])
        and ("feature" in stderr.lower() or "column" in stderr.lower())
    ):
        return "feature_name_error"
    if "KeyError" in stderr and any(col in stderr for col in state["dataset_columns"]):
        return "column_error"
    if "ConvergenceWarning" in stderr:
        return "convergence_failure"
    if "TypeError" in stderr:
        return "type_error"
    if failure_type in FAILURE_TAXONOMY:
        return failure_type

    return None


async def failure_diagnostician_node(
    state: RegressionState, experiment_result: ExperimentResult
) -> Dict[str, str]:
    failure_type = _rule_based_classify(experiment_result, state)

    if not failure_type:
        router = LLMRouter()
        raw = await router.call(
            task_type="analysis",
            system_prompt=(
                "You are an ML debugging expert for regression problems. Classify the failure into exactly one of these types: "
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
        leakage_warnings=state.get("leakage_warnings", []),
        metric_name=state.get("evaluation_metric", "rmse"),
    )

    return {
        "failure_type": failure_type,
        "fix_strategy": failure_type,
        "fix_instructions": fix_instructions,
    }
