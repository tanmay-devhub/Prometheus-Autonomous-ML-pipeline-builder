import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sklearn.model_selection import train_test_split
from fastapi.responses import FileResponse, JSONResponse

from backend.config import UPLOAD_DIR
from backend.state import PrometheusState
from backend.db import get_job, save_job, list_jobs
from tasks import run_pipeline_task

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("")
async def create_job(
    file: UploadFile = File(...),
    description: str = Form(...),
):
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

    last_col = df.columns[-1]
    unique_vals = df[last_col].dropna().unique()
    is_classification = len(unique_vals) <= 10

    # ── In-distribution sample pool (for Any / 0 / 1 filters) ────────────────
    # Take up to 20 rows per class so the tester always has plenty of each.
    try:
        if is_classification:
            per_class = max(20, 60 // len(unique_vals))
            parts = [
                df[df[last_col] == v].sample(min(per_class, int((df[last_col] == v).sum())), random_state=42)
                for v in unique_vals
            ]
            sample_df = pd.concat(parts).sample(frac=1, random_state=42)
        else:
            sample_df = df.sample(min(60, len(df)), random_state=42)
    except Exception:
        sample_df = df.sample(min(60, len(df)), random_state=42)

    sample_rows = _rows(sample_df)

    # ── Held-out rows (rows NOT seen during training) ─────────────────────────
    # Reconstruct the same train/test split the generated code uses
    # (test_size=0.2, random_state=42, stratified on the last column).
    held_out_rows: list = []
    try:
        y_proxy = df[last_col]
        strat = y_proxy if is_classification else None
        _, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=strat)
        if is_classification:
            # Up to 15 per class from the held-out set
            per_class = max(15, 40 // len(unique_vals))
            parts = [
                test_df[test_df[last_col] == v].sample(
                    min(per_class, int((test_df[last_col] == v).sum())), random_state=7
                )
                for v in unique_vals if v in test_df[last_col].values
            ]
            held_out_df = pd.concat(parts).sample(frac=1, random_state=7)
        else:
            held_out_df = test_df.sample(min(40, len(test_df)), random_state=7)
        held_out_rows = _rows(held_out_df)
    except Exception:
        held_out_rows = []

    row_count = len(df)

    initial_state: PrometheusState = {
        "job_id": job_id,
        "user_description": description,
        "dataset_path": dataset_path,
        "dataset_columns": columns,
        "dataset_sample_rows": sample_rows,
        "dataset_held_out_rows": held_out_rows,
        "dataset_row_count": row_count,
        "task_type": None,
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
        "winning_experiment": state.get("winning_experiment", {}).get("architecture_name") if state.get("winning_experiment") else None,
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
        "class_imbalance_detected": state.get("class_imbalance_detected"),
        "imbalance_ratio": state.get("imbalance_ratio"),
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
        encoding_map = save_obj.get("encoding_map")

        if encoding_map:
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
                    # fillna("nan") matches training's fillna('nan') so NaN columns align correctly
                    col_series = df[col].apply(
                        lambda x: float("nan") if x is None else x
                    ).fillna("nan").astype(str)
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

            pred_raw = model.predict(df)[0]
            if hasattr(pred_raw, "item"):
                pred_raw = pred_raw.item()

            reverse_map = encoding_map.get("reverse_target_mapping", {})
            if reverse_map:
                try:
                    prediction = reverse_map.get(int(round(float(pred_raw))), str(pred_raw))
                except (ValueError, TypeError):
                    prediction = str(pred_raw)
            else:
                prediction = pred_raw

            probability = None
            if hasattr(model, "predict_proba") and state.get("task_type") == "binary_classification":
                probability = round(float(model.predict_proba(df)[0][1]), 4)

            return {"prediction": prediction, "probability": probability, "target_column": target_col}

        else:
            # Legacy pkl format (without encoding_map)
            cat_encodings = save_obj.get("cat_encodings", {})
            num_medians = save_obj.get("num_medians", {})
            feature_names = save_obj.get("feature_names", [])

            target_col = state.get("target_column", "")
            feature_cols = feature_names or [c for c in state.get("dataset_columns", []) if c != target_col]

            row = {col: body.get(col) for col in feature_cols}
            df = pd.DataFrame([row])

            for col, mapping in cat_encodings.items():
                if col in df.columns:
                    df[col] = df[col].fillna("missing").astype(str).map(mapping).fillna(len(mapping)).astype(int)

            for col, med in num_medians.items():
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(med)

            for col in df.columns:
                if col not in cat_encodings and col not in num_medians:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            if feature_names:
                df = df.reindex(columns=feature_names, fill_value=0)

            prediction = model.predict(df)[0]
            if hasattr(prediction, "item"):
                prediction = prediction.item()

            probability = None
            if hasattr(model, "predict_proba") and state.get("task_type") == "binary_classification":
                probability = round(float(model.predict_proba(df)[0][1]), 4)

            return {"prediction": prediction, "probability": probability, "target_column": target_col}

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
    return {
        "plain_english_explanation": state.get("plain_english_explanation"),
        "shap_features": profile.get("shap_features", []),
        "winning_justification": state.get("winning_justification"),
    }
