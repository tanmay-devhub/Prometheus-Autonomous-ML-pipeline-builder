import json
from typing import Any, Dict

from backend.state import PrometheusState, ExperimentResult
from backend.llm.router import LLMRouter

FIX_STRATEGIES = {
    "syntax_error": (
        "The generated code has a Python syntax error. Rewrite the entire script from scratch, "
        "paying careful attention to proper Python syntax. Error: {error_message}"
    ),
    "import_error": (
        "The code imports a library that is not available. Remove all imports except: "
        "pandas, numpy, sklearn, xgboost, lightgbm, scipy, json, sys, os, warnings. "
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
    "convergence_failure": (
        "The model did not converge. Increase max_iter to 10000, reduce learning rate if applicable, "
        "add feature scaling before the model."
    ),
    "memory_error": (
        "The model ran out of memory. Switch to a simpler model with fewer parameters, or add a "
        "data sampling step that uses only 50% of training data."
    ),
    "timeout_error": (
        "Execution timed out. Use a faster model (LogisticRegression or LGBMClassifier/LGBMRegressor), "
        "reduce n_estimators to 50 if using tree models."
    ),
    "output_parse_error": (
        "The script did not print valid JSON on the last line. Ensure the very last print statement "
        "in the script prints exactly: "
        "print(json.dumps({{'metric_name': 'roc_auc', 'metric_value': 0.85, 'model_type': 'Model', "
        "'train_samples': 100, 'test_samples': 25}}))"
    ),
    "poor_metric": (
        "The model performance is poor. Try: (1) adding more preprocessing, (2) feature scaling, "
        "(3) handling missing values differently, (4) if classification with imbalance, "
        "add class_weight='balanced'."
    ),
    "suspicious_metric": (
        "The metric is suspiciously perfect, suggesting data leakage. Review all features and remove "
        "any that are too correlated with the target. Leakage warnings from profiling: {leakage_warnings}"
    ),
}

FAILURE_TAXONOMY = [
    "syntax_error", "import_error", "column_error", "type_error",
    "convergence_failure", "memory_error", "timeout_error",
    "output_parse_error", "poor_metric", "suspicious_metric",
]


def _rule_based_classify(experiment_result: ExperimentResult, state: PrometheusState) -> str | None:
    error_type = experiment_result.get("error_type") or ""
    stderr = experiment_result.get("stderr") or ""
    metrics = experiment_result.get("parsed_metrics") or {}
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
    if "KeyError" in stderr and any(col in stderr for col in state["dataset_columns"]):
        return "column_error"
    if "ConvergenceWarning" in stderr:
        return "convergence_failure"
    if "TypeError" in stderr:
        return "type_error"

    metric_val = metrics.get(state["evaluation_metric"], 0)
    if state["evaluation_metric"] == "roc_auc" and metric_val > 0.99:
        return "suspicious_metric"

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
                "You are an ML debugging expert. Classify the failure into exactly one of these types: "
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
    )

    return {
        "failure_type": failure_type,
        "fix_strategy": failure_type,
        "fix_instructions": fix_instructions,
    }
