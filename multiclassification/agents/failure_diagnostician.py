import json
from typing import Any, Dict

from multiclassification.state import MultiClassState, ExperimentResult
from shared.llm.router import LLMRouter

FIX_STRATEGIES = {
    "syntax_error": (
        "The generated code has a Python syntax error. Rewrite the entire script from scratch, "
        "paying careful attention to proper Python syntax. Error: {error_message}"
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
    "multiclass_config_error": (
        "The model is not configured for multiclass classification. "
        "Task: multiclass_classification. Number of classes: {num_classes}. "
        "For XGBClassifier: set objective='multi:softprob', num_class={num_classes}. "
        "For LGBMClassifier: set objective='multiclass', num_class={num_classes}. "
        "For LogisticRegression: set multi_class='multinomial', solver='lbfgs'."
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
        "Execution timed out. Use a faster model (LogisticRegression or LGBMClassifier), "
        "reduce n_estimators to 50 if using tree models."
    ),
    "output_parse_error": (
        "The script did not print valid JSON on the last line. "
        "Task type: multiclass_classification. Evaluation metric: {metric_name}. "
        "Ensure the very last print statement outputs exactly this structure:\n"
        "print(json.dumps({{'metric_name': '{metric_name}', 'metric_value': <float>, "
        "'accuracy': <float>, 'f1_macro': <float>, 'f1_weighted': <float>, "
        "'num_classes': <int>, 'class_names': <list>, 'per_class_f1': <dict>, "
        "'model_type': '<name>', 'train_samples': <int>, 'test_samples': <int>}}))\n"
        "Do NOT include 'encoding_map' or any large objects in this final JSON line."
    ),
    "poor_metric": (
        "The model performance is poor for multiclass classification. Try: "
        "(1) adding class_weight='balanced', "
        "(2) feature scaling with StandardScaler, "
        "(3) increasing n_estimators or max_iter, "
        "(4) checking for class imbalance and applying SMOTE or resampling."
    ),
    "suspicious_metric": (
        "The metric is suspiciously perfect, suggesting data leakage. Review all features and remove "
        "any that are too correlated with the target. Leakage warnings from profiling: {leakage_warnings}"
    ),
    "feature_name_error": (
        "XGBoost/LightGBM requires feature names without special characters (<, >, [, ], spaces, etc.). "
        "After any pd.get_dummies() call, sanitize column names using: "
        "df.columns = [re.sub(r'[^A-Za-z0-9_]', '_', c) for c in df.columns]. "
        "Apply the same sanitization to both train and test DataFrames."
    ),
    "label_encoder_error": (
        "The LabelEncoder failed on the target column. Ensure the target column is cast to str before "
        "fitting: le_target.fit(df[target_col].astype(str)). "
        "Also ensure transform uses the same dtype: le_target.transform(df[target_col].astype(str))."
    ),
}

FAILURE_TAXONOMY = [
    "syntax_error", "import_error", "column_error", "type_error",
    "multiclass_config_error", "label_encoder_error", "feature_name_error",
    "convergence_failure", "memory_error", "timeout_error",
    "output_parse_error", "poor_metric", "suspicious_metric",
]


def _rule_based_classify(experiment_result: ExperimentResult, state: MultiClassState) -> str | None:
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
    if "num_class" in stderr and ("XGB" in stderr or "LGB" in stderr):
        return "multiclass_config_error"
    if "multi:softprob" in stderr or "multiclass" in stderr and "objective" in stderr.lower():
        return "multiclass_config_error"
    if "LabelEncoder" in stderr and ("fit" in stderr or "transform" in stderr):
        return "label_encoder_error"
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
    state: MultiClassState, experiment_result: ExperimentResult
) -> Dict[str, str]:
    failure_type = _rule_based_classify(experiment_result, state)

    if not failure_type:
        router = LLMRouter()
        raw = await router.call(
            task_type="analysis",
            system_prompt=(
                "You are an ML debugging expert for multiclass classification. "
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
    num_classes = state.get("num_classes", 3)
    fix_instructions = template.format(
        error_message=experiment_result.get("error_message", ""),
        column_list=state["dataset_columns"],
        leakage_warnings=state.get("leakage_warnings", []),
        task_type="multiclass_classification",
        metric_name=state.get("evaluation_metric", "f1_macro"),
        num_classes=num_classes,
    )

    return {
        "failure_type": failure_type,
        "fix_strategy": failure_type,
        "fix_instructions": fix_instructions,
    }
