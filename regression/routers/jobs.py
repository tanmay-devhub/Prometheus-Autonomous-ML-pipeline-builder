import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sklearn.model_selection import train_test_split
from fastapi.responses import FileResponse

from regression.config import UPLOAD_DIR
from regression.state import RegressionState
from regression.db import get_job, save_job, list_jobs
from regression.tasks import run_pipeline_task

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("")
async def create_job(file: UploadFile = File(...), description: str = Form(...)):
    job_id = str(uuid.uuid4())
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    dataset_path = os.path.join(UPLOAD_DIR, f"{job_id}.csv")

    contents = await file.read()
    with open(dataset_path, "wb") as f:
        f.write(contents)

    df = pd.read_csv(dataset_path)
    columns = df.columns.tolist()

    def _clean(v: Any) -> Any:
        if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
            return None
        return v

    def _rows(frame: pd.DataFrame) -> list:
        return [{k: _clean(v) for k, v in row.items()} for row in frame.to_dict(orient="records")]

    # For regression: no stratify, just sample rows
    try:
        sample_df = df.sample(min(60, len(df)), random_state=42)
    except Exception:
        sample_df = df.head(60)

    sample_rows = _rows(sample_df)

    held_out_rows: list = []
    try:
        _, test_df = train_test_split(df, test_size=0.2, random_state=42)
        held_out_df = test_df.sample(min(40, len(test_df)), random_state=7)
        held_out_rows = _rows(held_out_df)
    except Exception:
        held_out_rows = []

    initial_state: RegressionState = {
        "job_id": job_id,
        "user_description": description,
        "dataset_path": dataset_path,
        "dataset_columns": columns,
        "dataset_sample_rows": sample_rows,
        "dataset_held_out_rows": held_out_rows,
        "dataset_row_count": len(df),
        "task_type": "regression",
        "target_column": None,
        "evaluation_metric": None,
        "domain_flags": [],
        "problem_analysis_raw": None,
        "problem_approved": False,
        "model_approved": False,
        "profile_report": None,
        "validation_warnings": [],
        "leakage_warnings": [],
        "class_imbalance_detected": False,
        "imbalance_ratio": None,
        "target_min": None,
        "target_max": None,
        "target_mean": None,
        "target_std": None,
        "prediction_range_warning": False,
        "architectures": [],
        "experiment_results": [],
        "current_retry_count": 0,
        "winning_experiment": None,
        "winning_justification": None,
        "model_card": None,
        "shap_plot_path": None,
        "generated_endpoint_code": None,
        "generated_requirements": None,
        "plain_english_explanation": None,
        "encoding_map": None,
        "current_phase": "initializing",
        "error_message": None,
        "debug_log": [],
    }

    save_job(job_id, initial_state)
    run_pipeline_task.delay(job_id)
    return {"job_id": job_id, "status": "running"}


@router.get("/{job_id}")
async def get_full_job(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    return state


@router.get("/{job_id}/status")
async def get_job_status(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "current_phase": state.get("current_phase"),
        "error_message": state.get("error_message"),
        "task_type": state.get("task_type"),
        "target_column": state.get("target_column"),
        "evaluation_metric": state.get("evaluation_metric"),
        "experiment_count": len(state.get("experiment_results", [])),
        "winning_experiment": state.get("winning_experiment", {}).get("architecture_name")
            if state.get("winning_experiment") else None,
    }


@router.get("/{job_id}/profile")
async def get_profile(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    if not state.get("profile_report"):
        raise HTTPException(status_code=404, detail="Profile not yet available")
    return {
        "profile_report": state["profile_report"],
        "validation_warnings": state.get("validation_warnings", []),
        "leakage_warnings": state.get("leakage_warnings", []),
        "class_imbalance_detected": False,
        "imbalance_ratio": None,
        "target_min": state.get("target_min"),
        "target_max": state.get("target_max"),
        "target_mean": state.get("target_mean"),
        "target_std": state.get("target_std"),
    }


@router.get("/{job_id}/experiments")
async def get_experiments(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"experiment_results": state.get("experiment_results", [])}


@router.get("/{job_id}/debug-log")
async def get_debug_log(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"debug_log": state.get("debug_log", [])}


@router.get("/{job_id}/model-card")
async def get_model_card(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    if not state.get("model_card"):
        raise HTTPException(status_code=404, detail="Model card not yet available")
    return {"model_card": state["model_card"]}


@router.get("/{job_id}/endpoint-code")
async def get_endpoint_code(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    if not state.get("generated_endpoint_code"):
        raise HTTPException(status_code=404, detail="Endpoint code not yet available")
    return {
        "endpoint_code": state["generated_endpoint_code"],
        "requirements": state.get("generated_requirements", ""),
    }


@router.post("/{job_id}/test-predict")
async def test_predict(job_id: str, body: Dict[str, Any]):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    pkl_path = state.get("model_pkl_path")
    if not pkl_path or not os.path.exists(pkl_path):
        raise HTTPException(status_code=404, detail="model.pkl not available — complete the pipeline first")
    try:
        import pickle
        with open(pkl_path, "rb") as f:
            save_obj = pickle.load(f)

        if not isinstance(save_obj, dict):
            save_obj = {"model": save_obj}

        model = save_obj["model"]
        encoding_map = save_obj.get("encoding_map", {})

        target_col = encoding_map.get("target_column") or state.get("target_column", "")
        orig_cols = encoding_map.get("original_feature_columns") or \
                    [c for c in state.get("dataset_columns", []) if c != target_col]

        row = {col: body.get(col) for col in orig_cols}
        df = pd.DataFrame([row])

        # Fix numeric strings
        for col in list(df.columns):
            if df[col].dtype == "object":
                conv = pd.to_numeric(df[col], errors="coerce")
                if not conv.isna().all():
                    df[col] = conv

        # Binary encoding
        for col, enc in encoding_map.get("binary_encoders", {}).items():
            if col in df.columns:
                df[col] = df[col].fillna("missing").astype(str).map(enc["mapping"]).fillna(0).astype(int)

        # One-hot encoding
        for col, enc in encoding_map.get("multi_encoders", {}).items():
            if col in df.columns:
                col_to_cat = enc.get("col_to_category", {})
                col_series = df[col].apply(lambda x: float("nan") if x is None else x).fillna("nan").astype(str)
                for enc_col in enc.get("encoded_columns", []):
                    category = col_to_cat.get(enc_col) if col_to_cat else enc_col[len(col) + 1:]
                    df[enc_col] = (col_series == category).astype(int)
                df = df.drop(columns=[col])

        # Numeric imputation
        for col, med in encoding_map.get("num_medians", {}).items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(med)

        # Align to training feature order
        feature_cols = encoding_map.get("feature_columns_after_encoding", [])
        if feature_cols:
            df = df.reindex(columns=feature_cols, fill_value=0)

        raw_pred = float(model.predict(df)[0])

        # Reverse log transform if applied during training
        if encoding_map.get("target_log_transformed"):
            prediction = float(np.expm1(raw_pred))
        else:
            prediction = raw_pred

        return {
            "prediction": round(prediction, 4),
            "prediction_formatted": f"{prediction:,.2f}",
            "target_column": target_col,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/model.pkl")
async def download_model_pkl(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    pkl_path = state.get("model_pkl_path")
    if not pkl_path or not os.path.exists(pkl_path):
        raise HTTPException(status_code=404, detail="model.pkl not available — run the full pipeline first")
    return FileResponse(pkl_path, filename="model.pkl", media_type="application/octet-stream")


@router.get("/{job_id}/explanation")
async def get_explanation(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    profile = state.get("profile_report") or {}
    winning = state.get("winning_experiment") or {}
    metrics = winning.get("parsed_metrics", {})
    return {
        "plain_english_explanation": state.get("plain_english_explanation"),
        "shap_features": profile.get("shap_features", []),
        "winning_justification": state.get("winning_justification"),
        "rmse": metrics.get("rmse"),
        "mae": metrics.get("mae"),
        "r2": metrics.get("r2"),
        "rmse_pct_of_mean": metrics.get("rmse_pct_of_mean"),
        "within_10_pct": metrics.get("within_10_pct"),
        "within_15_pct": metrics.get("within_15_pct"),
        "within_20_pct": metrics.get("within_20_pct"),
        "target_mean": metrics.get("target_mean"),
    }
