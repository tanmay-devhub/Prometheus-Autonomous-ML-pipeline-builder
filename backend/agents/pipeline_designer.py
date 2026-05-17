import json
from datetime import datetime
from typing import Any, Dict, List

from backend.state import PrometheusState
from backend.llm.router import LLMRouter
from backend.config import ALLOWED_MODEL_TYPES

SYSTEM_PROMPT = """You are an expert ML engineer designing machine learning pipelines.
You will receive a data profile and must propose exactly 2 different pipeline architectures.

The architectures must be meaningfully different — not just different hyperparameters of the same model.
Good contrast examples:
- A tree-based model vs a linear model
- A simple single model vs a more complex ensemble
- A model that handles missing values natively vs one that requires imputation

For each architecture, return a JSON object with exactly these fields:
{
  "name": "<short descriptive name, e.g. 'gradient_boosting_pipeline'>",
  "model_type": "<exact sklearn/xgboost/lightgbm class name>",
  "preprocessing_steps": [
    {"step": "<step name>", "transformer": "<exact transformer class>", "columns": "<which columns>", "reason": "<why>"}
  ],
  "hyperparameters": {"<param>": <value>},
  "handles_missing_natively": true|false,
  "handles_imbalance": true|false,
  "imbalance_strategy": "<none|class_weight|smote>",
  "justification": "<2 sentences explaining why this architecture fits this specific dataset>",
  "expected_strength": "<what this model is good at>",
  "expected_weakness": "<what this model struggles with>"
}

Return a JSON array of exactly 2 architecture objects.
Reference the actual column names and data characteristics from the profile in your justification.
Only return valid JSON. No markdown, no backticks, no explanation.

Allowed model types ONLY:
- LogisticRegression (classification)
- RandomForestClassifier (classification)
- GradientBoostingClassifier (classification)
- XGBClassifier (classification)
- LGBMClassifier (classification)
- Ridge (regression)
- RandomForestRegressor (regression)
- GradientBoostingRegressor (regression)
- XGBRegressor (regression)
- LGBMRegressor (regression)"""


async def pipeline_designer_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    profile = state.get("profile_report", {})
    columns = state["dataset_columns"]
    task_type = state["task_type"]
    target_col = state["target_column"]
    imbalance = state["class_imbalance_detected"]
    imbalance_ratio = state.get("imbalance_ratio")

    col_stats = profile.get("columns", [])
    null_rates = {c["column"]: c["null_pct"] for c in col_stats}

    user_message = (
        f"Task type: {task_type}\n"
        f"Target column: {target_col}\n"
        f"Evaluation metric: {state['evaluation_metric']}\n"
        f"Columns: {columns}\n"
        f"Column dtypes and null rates: {json.dumps(null_rates)}\n"
        f"Row count: {profile.get('row_count', 'unknown')}\n"
        f"Validation warnings: {json.dumps(state['validation_warnings'])}\n"
        f"Leakage warnings: {state['leakage_warnings']}\n"
        f"Class imbalance detected: {imbalance}\n"
        f"Imbalance ratio: {imbalance_ratio}\n"
        f"LLM data insights:\n{profile.get('llm_interpretation', '')}"
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
            current_message = "Your previous response was not valid JSON. Return only the JSON array of 2 architectures, nothing else."
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

    # Enforce: if imbalance detected, at least one must handle it
    if imbalance and not any(a.get("handles_imbalance") for a in architectures):
        architectures[0]["handles_imbalance"] = True
        architectures[0]["imbalance_strategy"] = "class_weight"

    state["architectures"] = architectures
    state["current_phase"] = "design_complete"
    state["debug_log"].append({
        "phase": "pipeline_designer",
        "timestamp": datetime.utcnow().isoformat(),
        "architectures": [a["name"] for a in architectures],
        "retries_used": retries,
    })

    return state
