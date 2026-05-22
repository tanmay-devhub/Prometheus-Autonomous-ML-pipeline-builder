import json
import os
import uuid
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sklearn.model_selection import train_test_split

from shared.llm.router import LLMRouter

router = APIRouter(prefix="/auto", tags=["auto"])

DETECTION_SYSTEM = "You are an expert ML engineer. Return only valid JSON, no markdown, no backticks."

DETECTION_PROMPT = """Analyze this dataset and user description to determine the correct ML task type.

User description: {description}

Dataset columns: {columns}

Sample rows (first 5):
{sample_rows}

Choose exactly one task type:
- "binary_classification" — target has exactly 2 distinct values (Yes/No, 0/1, survived/died, etc.)
- "multiclass_classification" — target has 3 to 20 distinct categorical labels (species, quality grades, news categories, etc.)
- "regression" — target is a continuous numeric variable (prices, temperatures, salaries, scores, etc.)
- "timeseries" — dataset has a date/time column AND the goal is to forecast future values over time (stock prices, sales, temperatures, traffic, energy)

Return JSON:
{{
  "task_type": "binary_classification" | "multiclass_classification" | "regression" | "timeseries",
  "target_column": "<exact column name from the dataset>",
  "reasoning": "<one sentence explaining why>",
  "confidence": 0.0-1.0
}}"""


def _clean(v: Any) -> Any:
    if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
        return None
    return v


def _rows(frame: pd.DataFrame) -> list:
    return [{k: _clean(v) for k, v in row.items()} for row in frame.to_dict(orient="records")]


async def _detect_task_type(columns: list, sample_rows: list, description: str) -> dict:
    llm = LLMRouter()
    raw = await llm.call(
        task_type="analysis",
        system_prompt=DETECTION_SYSTEM,
        user_message=DETECTION_PROMPT.format(
            description=description,
            columns=columns,
            sample_rows=json.dumps(sample_rows, default=str, indent=2),
        ),
    )
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        # Safe fallback: guess from last column unique count
        return {
            "task_type": "binary_classification",
            "target_column": columns[-1] if columns else "",
            "reasoning": "LLM response was not valid JSON — defaulting to binary classification.",
            "confidence": 0.3,
        }


@router.post("/jobs")
async def auto_create_job(
    file: UploadFile = File(...),
    description: str = Form(...),
):
    contents = await file.read()
    job_id = str(uuid.uuid4())

    try:
        df = pd.read_csv(BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if df.empty or len(df.columns) < 2:
        raise HTTPException(status_code=400, detail="Dataset must have at least 2 columns and 1 row.")

    columns = df.columns.tolist()
    sample_rows = _rows(df.head(5))

    # Detect task type
    detection = await _detect_task_type(columns, sample_rows, description)
    task_type = detection.get("task_type", "binary_classification")
    target_column = detection.get("target_column") or columns[-1]

    # Ensure target_column is valid
    if target_column not in columns:
        target_column = columns[-1]

    # Route to the appropriate service
    if task_type == "regression":
        from regression.config import UPLOAD_DIR, ARTIFACTS_DIR
        from regression.db import save_job
        from regression.tasks import run_pipeline_task
        redirect_to = "regression"

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        dataset_path = os.path.join(UPLOAD_DIR, f"{job_id}.csv")
        with open(dataset_path, "wb") as f:
            f.write(contents)

        try:
            sample_df = df.sample(min(60, len(df)), random_state=42)
        except Exception:
            sample_df = df.head(60)

        held_out_rows: list = []
        try:
            _, test_df = train_test_split(df, test_size=0.2, random_state=42)
            held_out_rows = _rows(test_df.sample(min(40, len(test_df)), random_state=7))
        except Exception:
            pass

        initial_state = {
            "job_id": job_id, "user_description": description,
            "dataset_path": dataset_path, "dataset_columns": columns,
            "dataset_sample_rows": _rows(sample_df),
            "dataset_held_out_rows": held_out_rows,
            "dataset_row_count": len(df),
            "task_type": None, "target_column": None, "evaluation_metric": None,
            "domain_flags": [], "problem_analysis_raw": None,
            "problem_approved": False, "model_approved": False,
            "profile_report": None, "validation_warnings": [], "leakage_warnings": [],
            "skewness_warning": None, "log_transform_applied": False,
            "target_min": None, "target_max": None, "target_mean": None,
            "target_std": None, "prediction_range_warning": None,
            "architectures": [], "experiment_results": [], "current_retry_count": 0,
            "winning_experiment": None, "winning_justification": None,
            "model_card": None, "shap_plot_path": None,
            "generated_endpoint_code": None, "generated_requirements": None,
            "plain_english_explanation": None, "encoding_map": None,
            "current_phase": "initializing", "error_message": None, "debug_log": [],
        }
        save_job(job_id, initial_state)
        run_pipeline_task.delay(job_id)

    elif task_type == "multiclass_classification":
        from multiclassification.config import UPLOAD_DIR, ARTIFACTS_DIR
        from multiclassification.db import save_job
        from multiclassification.tasks import run_pipeline_task
        redirect_to = "multiclassification"

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        dataset_path = os.path.join(UPLOAD_DIR, f"{job_id}.csv")
        with open(dataset_path, "wb") as f:
            f.write(contents)

        unique_vals = df[target_column].dropna().unique() if target_column in df.columns else []
        num_classes = len(unique_vals)
        class_names = [str(v) for v in unique_vals]
        class_distribution = {str(k): int(v) for k, v in df[target_column].value_counts().items()} if target_column in df.columns else {}

        per_class = max(10, 60 // max(num_classes, 1))
        try:
            parts = [df[df[target_column] == v].sample(min(per_class, int((df[target_column] == v).sum())), random_state=42) for v in unique_vals]
            sample_df = pd.concat(parts).sample(frac=1, random_state=42) if parts else df.head(60)
        except Exception:
            sample_df = df.head(60)

        held_out_rows = []
        try:
            strat = df[target_column] if target_column in df.columns and df[target_column].value_counts().min() >= 2 else None
            _, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=strat)
            parts_h = [test_df[test_df[target_column] == v].sample(min(10, int((test_df[target_column] == v).sum())), random_state=7) for v in unique_vals if v in test_df[target_column].values]
            held_out_rows = _rows(pd.concat(parts_h).sample(frac=1, random_state=7)) if parts_h else []
        except Exception:
            pass

        initial_state = {
            "job_id": job_id, "user_description": description,
            "dataset_path": dataset_path, "dataset_columns": columns,
            "dataset_sample_rows": _rows(sample_df),
            "dataset_held_out_rows": held_out_rows,
            "dataset_row_count": len(df),
            "task_type": None, "target_column": None, "evaluation_metric": None,
            "domain_flags": [], "problem_analysis_raw": None,
            "problem_approved": False, "model_approved": False,
            "profile_report": None, "validation_warnings": [], "leakage_warnings": [],
            "class_imbalance_detected": False, "imbalance_ratio": None,
            "class_distribution": class_distribution,
            "num_classes": num_classes, "class_names": class_names,
            "imbalanced_classes": [], "per_class_metrics": None, "encoding_map": None,
            "architectures": [], "experiment_results": [], "current_retry_count": 0,
            "winning_experiment": None, "winning_justification": None,
            "model_card": None, "shap_plot_path": None,
            "generated_endpoint_code": None, "generated_requirements": None,
            "plain_english_explanation": None,
            "current_phase": "initializing", "error_message": None, "debug_log": [],
        }
        save_job(job_id, initial_state)
        run_pipeline_task.delay(job_id)

    elif task_type == "timeseries":
        from timeseries.config import UPLOAD_DIR, ARTIFACTS_DIR
        from timeseries.db import save_job
        from timeseries.tasks import run_pipeline_task
        redirect_to = "timeseries"

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        dataset_path = os.path.join(UPLOAD_DIR, f"{job_id}.csv")
        with open(dataset_path, "wb") as f:
            f.write(contents)

        sample_rows_ts = _rows(df.head(5))
        held_out_rows_ts = _rows(df.tail(min(20, len(df))))

        initial_state = {
            "job_id": job_id, "user_description": description,
            "dataset_path": dataset_path, "dataset_columns": columns,
            "dataset_sample_rows": sample_rows_ts,
            "dataset_held_out_rows": held_out_rows_ts,
            "dataset_row_count": len(df),
            "task_type": None, "date_column": None, "target_column": None,
            "evaluation_metric": None, "domain_flags": [], "problem_analysis_raw": None,
            "problem_approved": False, "model_approved": False,
            "frequency": None, "forecast_horizon": 30, "sequence_length": 14,
            "has_seasonality": False, "has_trend": False, "is_stationary": True,
            "lag_features_used": [], "rolling_features_used": [],
            "train_cutoff_date": None, "test_cutoff_date": None,
            "forecast_values": None, "forecast_dates": None,
            "profile_report": None, "validation_warnings": [], "leakage_warnings": [],
            "architectures": [], "experiment_results": [], "current_retry_count": 0,
            "winning_experiment": None, "winning_justification": None,
            "model_card": None, "shap_plot_path": None,
            "generated_endpoint_code": None, "generated_requirements": None,
            "plain_english_explanation": None,
            "current_phase": "initializing", "error_message": None, "debug_log": [],
        }
        save_job(job_id, initial_state)
        run_pipeline_task.delay(job_id)

    else:
        # Default: binary_classification
        task_type = "binary_classification"
        from classification.config import UPLOAD_DIR, ARTIFACTS_DIR
        from classification.db import save_job
        from classification.tasks import run_pipeline_task
        redirect_to = "classification"

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        dataset_path = os.path.join(UPLOAD_DIR, f"{job_id}.csv")
        with open(dataset_path, "wb") as f:
            f.write(contents)

        unique_vals = df[target_column].dropna().unique() if target_column in df.columns else []
        is_cls = len(unique_vals) <= 10

        try:
            if is_cls and len(unique_vals) > 0:
                per_class = max(20, 60 // len(unique_vals))
                parts = [df[df[target_column] == v].sample(min(per_class, int((df[target_column] == v).sum())), random_state=42) for v in unique_vals]
                sample_df = pd.concat(parts).sample(frac=1, random_state=42)
            else:
                sample_df = df.sample(min(60, len(df)), random_state=42)
        except Exception:
            sample_df = df.head(60)

        held_out_rows = []
        try:
            strat = df[target_column] if is_cls and target_column in df.columns and df[target_column].value_counts().min() >= 2 else None
            _, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=strat)
            if is_cls and len(unique_vals) > 0:
                per_class_h = max(15, 40 // len(unique_vals))
                parts_h = [test_df[test_df[target_column] == v].sample(min(per_class_h, int((test_df[target_column] == v).sum())), random_state=7) for v in unique_vals if v in test_df[target_column].values]
                held_out_rows = _rows(pd.concat(parts_h).sample(frac=1, random_state=7))
            else:
                held_out_rows = _rows(test_df.sample(min(40, len(test_df)), random_state=7))
        except Exception:
            pass

        initial_state = {
            "job_id": job_id, "user_description": description,
            "dataset_path": dataset_path, "dataset_columns": columns,
            "dataset_sample_rows": _rows(sample_df),
            "dataset_held_out_rows": held_out_rows,
            "dataset_row_count": len(df),
            "task_type": None, "target_column": None, "evaluation_metric": None,
            "domain_flags": [], "problem_analysis_raw": None,
            "problem_approved": False, "model_approved": False,
            "profile_report": None, "validation_warnings": [], "leakage_warnings": [],
            "class_imbalance_detected": False, "imbalance_ratio": None, "class_distribution": {},
            "architectures": [], "experiment_results": [], "current_retry_count": 0,
            "winning_experiment": None, "winning_justification": None,
            "model_card": None, "shap_plot_path": None,
            "generated_endpoint_code": None, "generated_requirements": None,
            "plain_english_explanation": None, "encoding_map": None,
            "current_phase": "initializing", "error_message": None, "debug_log": [],
        }
        save_job(job_id, initial_state)
        run_pipeline_task.delay(job_id)

    return {
        "job_id": job_id,
        "task_type": task_type,
        "redirect_to": redirect_to,
        "target_column": target_column,
        "confidence": detection.get("confidence", 0.8),
        "reasoning": detection.get("reasoning", ""),
    }
