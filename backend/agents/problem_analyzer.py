import json
import asyncio
from datetime import datetime
from typing import Any, Dict

from backend.state import PrometheusState
from backend.llm.router import LLMRouter
from backend.config import ALLOWED_TASK_TYPES, ALLOWED_METRICS

SYSTEM_PROMPT = """You are an expert ML engineer analyzing a machine learning problem.
You will be given:
1. A plain English description of what the user wants to predict
2. The column names of their dataset
3. Five sample rows of their dataset

Your job is to return a JSON object with exactly these fields:
{
  "task_type": "binary_classification" | "regression",
  "target_column": "<exact column name from the dataset>",
  "evaluation_metric": "roc_auc" | "rmse" | "mae" | "r2",
  "confidence": 0.0-1.0,
  "reasoning": "<one sentence explaining why you chose this task type>",
  "domain_flags": ["<any domain-specific flags, e.g. medical_data, financial_data, time_series_risk>"],
  "alternative_target": "<if you are unsure about target column, suggest an alternative>",
  "warnings": ["<any immediate concerns about the problem setup>"]
}

Rules:
- target_column MUST be an exact match to one of the provided column names
- If you cannot determine the target column with confidence > 0.7, set confidence below 0.7 and explain in warnings
- Only return valid JSON. No markdown, no explanation, no backticks."""

CORRECTIVE_JSON_PROMPT = "Your previous response was not valid JSON. Return only the JSON object, nothing else."
CORRECTIVE_COLUMN_PROMPT = (
    "The target_column you returned does not exist in the dataset. "
    "You must choose target_column from exactly these column names: {columns}. "
    "Return only the corrected JSON object."
)


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

        # Validate target_column
        if parsed.get("target_column") not in columns:
            retries += 1
            current_user_message = CORRECTIVE_COLUMN_PROMPT.format(columns=columns)
            parsed = None
            continue

        # Validate task_type
        if parsed.get("task_type") not in ALLOWED_TASK_TYPES:
            retries += 1
            current_user_message = (
                f"task_type must be one of {list(ALLOWED_TASK_TYPES)}. Return corrected JSON only."
            )
            parsed = None
            continue

        break

    if parsed is None:
        state["error_message"] = "Problem analyzer failed to return valid analysis after 3 retries."
        state["current_phase"] = "failed"
        return state

    state["task_type"] = parsed.get("task_type")
    state["target_column"] = parsed.get("target_column")
    state["evaluation_metric"] = parsed.get("evaluation_metric")
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
