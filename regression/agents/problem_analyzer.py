import json
from datetime import datetime
from typing import Any, Dict

import pandas as pd
from sklearn.model_selection import train_test_split

from regression.state import RegressionState
from shared.llm.router import LLMRouter
from regression.config import ALLOWED_TASK_TYPES, ALLOWED_METRICS

SYSTEM_PROMPT = """You are an expert ML engineer analyzing a regression problem.
You will be given:
1. A plain English description of what the user wants to predict
2. The column names of their dataset
3. Five sample rows of their dataset

Your job is to return a JSON object with exactly these fields:
{
  "task_type": "regression",
  "target_column": "<exact column name from the dataset>",
  "evaluation_metric": "rmse" | "mae" | "r2",
  "confidence": 0.0-1.0,
  "reasoning": "<one sentence explaining your choice>",
  "domain_flags": ["<domain-specific flags, e.g. housing_data, financial_data, medical_data>"],
  "alternative_target": "<if unsure about target, suggest an alternative>",
  "warnings": ["<any concerns about the problem setup>"]
}

Rules:
- task_type MUST always be "regression" — this service only handles regression
- target_column MUST be an exact match to one of the provided column names
- The target column should be a continuous numeric variable (prices, temperatures, salaries, counts, etc.)
- evaluation_metric: use "rmse" by default, "mae" if the user mentions outlier robustness, "r2" if they mention variance explained
- Only return valid JSON. No markdown, no explanation, no backticks."""

CORRECTIVE_JSON_PROMPT = "Your previous response was not valid JSON. Return only the JSON object, nothing else."
CORRECTIVE_COLUMN_PROMPT = (
    "The target_column you returned does not exist in the dataset. "
    "You must choose target_column from exactly these column names: {columns}. "
    "Return only the corrected JSON object."
)


def _recompute_held_out_rows(state: RegressionState) -> None:
    target_col = state["target_column"]
    try:
        df = pd.read_csv(state["dataset_path"])
        df = df.dropna(subset=[target_col])

        def _clean(v: Any) -> Any:
            if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
                return None
            return v

        _, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=None)
        held_df = test_df.sample(min(40, len(test_df)), random_state=7)

        state["dataset_held_out_rows"] = [
            {k: _clean(v) for k, v in row.items()}
            for row in held_df.to_dict(orient="records")
        ]

        # Store target stats
        state["target_min"] = float(df[target_col].min())
        state["target_max"] = float(df[target_col].max())
        state["target_mean"] = float(df[target_col].mean())
        state["target_std"] = float(df[target_col].std())
    except Exception:
        pass


async def problem_analyzer_node(state: RegressionState) -> RegressionState:
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

        if parsed.get("target_column") not in columns:
            retries += 1
            current_user_message = CORRECTIVE_COLUMN_PROMPT.format(columns=columns)
            parsed = None
            continue

        # Force regression
        parsed["task_type"] = "regression"
        if parsed.get("evaluation_metric") not in ALLOWED_METRICS:
            parsed["evaluation_metric"] = "rmse"

        break

    if parsed is None:
        state["error_message"] = "Problem analyzer failed to return valid analysis after 3 retries."
        state["current_phase"] = "failed"
        return state

    state["task_type"] = "regression"
    state["target_column"] = parsed.get("target_column")
    state["evaluation_metric"] = parsed.get("evaluation_metric", "rmse")
    state["domain_flags"] = parsed.get("domain_flags", [])
    state["problem_analysis_raw"] = json.dumps(parsed)

    _recompute_held_out_rows(state)

    state["debug_log"].append({
        "phase": "problem_analyzer",
        "timestamp": datetime.utcnow().isoformat(),
        "output": parsed,
        "retries_used": retries,
    })

    state["current_phase"] = "awaiting_problem_approval"
    return state
