import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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
    # Replace NaN/Inf with None so they serialize to JSON null
    sample_rows = [
        {k: (None if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")) else v)
         for k, v in row.items()}
        for row in df.head(5).to_dict(orient="records")
    ]
    row_count = len(df)

    initial_state: PrometheusState = {
        "job_id": job_id,
        "user_description": description,
        "dataset_path": dataset_path,
        "dataset_columns": columns,
        "dataset_sample_rows": sample_rows,
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

        # Support both plain dict format and legacy pipeline format
        if isinstance(save_obj, dict) and "model" in save_obj:
            model = save_obj["model"]
            cat_encodings = save_obj.get("cat_encodings", {})
            num_medians = save_obj.get("num_medians", {})
            feature_names = save_obj.get("feature_names", [])
        else:
            model = save_obj  # legacy: raw model or pipeline
            cat_encodings = {}
            num_medians = {}
            feature_names = []

        target_col = state.get("target_column", "")
        feature_cols = feature_names or [c for c in state.get("dataset_columns", []) if c != target_col]

        row = {col: body.get(col) for col in feature_cols}
        df = pd.DataFrame([row])

        # Apply category encodings
        for col, mapping in cat_encodings.items():
            if col in df.columns:
                df[col] = df[col].fillna("missing").astype(str).map(mapping).fillna(len(mapping)).astype(int)

        # Apply numeric imputation
        for col, med in num_medians.items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(med)

        # Fill anything still missing
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
