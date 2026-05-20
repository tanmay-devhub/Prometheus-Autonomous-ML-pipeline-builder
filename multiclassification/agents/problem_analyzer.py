import json
import asyncio
from datetime import datetime
from typing import Any, Dict

import pandas as pd
from sklearn.model_selection import train_test_split

from multiclassification.state import MultiClassState
from shared.llm.router import LLMRouter
from multiclassification.config import ALLOWED_TASK_TYPES, ALLOWED_METRICS

SYSTEM_PROMPT = """You are an expert ML engineer analyzing a multiclass classification problem.
This service handles problems where the target column has 3 or more distinct categories.

You will be given:
1. A plain English description of what the user wants to predict
2. The column names of their dataset
3. Five sample rows of their dataset

Your job is to return a JSON object with exactly these fields:
{
  "task_type": "multiclass_classification",
  "target_column": "<exact column name from the dataset>",
  "num_classes": <integer, number of distinct classes>,
  "class_names": ["<class1>", "<class2>", ...],
  "evaluation_metric": "f1_macro" | "f1_weighted" | "accuracy" | "log_loss",
  "confidence": 0.0-1.0,
  "reasoning": "<one sentence explaining why this is multiclass>",
  "domain_flags": ["<any domain-specific flags>"],
  "class_balance_warning": true|false,
  "dominant_class": "<class name if one class > 50%, else null>",
  "warnings": ["<any immediate concerns about the problem setup>"]
}

Rules:
- task_type MUST always be "multiclass_classification"
- target_column MUST be an exact match to one of the provided column names
- num_classes must match the actual number of unique values in the target column
- evaluation_metric selection:
  * Balanced classes → use f1_macro
  * Imbalanced (one class > 50%) → use f1_weighted
  * Default to f1_macro if unsure
- Only return valid JSON. No markdown, no explanation, no backticks."""

CORRECTIVE_JSON_PROMPT = "Your previous response was not valid JSON. Return only the JSON object, nothing else."
CORRECTIVE_COLUMN_PROMPT = (
    "The target_column you returned does not exist in the dataset. "
    "You must choose target_column from exactly these column names: {columns}. "
    "Return only the corrected JSON object."
)


def _recompute_held_out_rows(state: MultiClassState) -> None:
    target_col = state["target_column"]
    try:
        df = pd.read_csv(state["dataset_path"])
        df = df.dropna(subset=[target_col])

        unique_vals = df[target_col].dropna().unique()

        def _clean(v: Any) -> Any:
            if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
                return None
            return v

        strat = df[target_col]
        min_class_count = strat.value_counts().min() if len(strat) > 0 else 0
        if strat.isna().any() or min_class_count < 2:
            strat = None

        _, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=strat)

        per_class = max(10, 40 // max(len(unique_vals), 1))
        parts = [
            test_df[test_df[target_col] == v].sample(
                min(per_class, int((test_df[target_col] == v).sum())),
                random_state=7,
            )
            for v in unique_vals
            if v in test_df[target_col].values
        ]
        held_df = pd.concat(parts).sample(frac=1, random_state=7)

        state["dataset_held_out_rows"] = [
            {k: _clean(v) for k, v in row.items()}
            for row in held_df.to_dict(orient="records")
        ]
    except Exception:
        pass


async def problem_analyzer_node(state: MultiClassState) -> MultiClassState:
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
    state["evaluation_metric"] = parsed.get("evaluation_metric", "f1_macro")
    state["domain_flags"] = parsed.get("domain_flags", [])
    state["num_classes"] = parsed.get("num_classes", 0)
    state["class_names"] = parsed.get("class_names", [])
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
