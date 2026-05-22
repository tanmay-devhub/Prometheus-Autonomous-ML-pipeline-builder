import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from timeseries.config import UPLOAD_DIR
from timeseries.state import TimeSeriesState
from timeseries.db import get_job, save_job, list_jobs
from timeseries.tasks import run_pipeline_task

router = APIRouter(prefix="/jobs", tags=["timeseries-jobs"])


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

    sample_rows = _rows(df.head(5))
    held_out_rows = _rows(df.tail(min(20, len(df))))

    initial_state: TimeSeriesState = {
        "job_id": job_id,
        "user_description": description,
        "dataset_path": dataset_path,
        "dataset_columns": columns,
        "dataset_sample_rows": sample_rows,
        "dataset_held_out_rows": held_out_rows,
        "dataset_row_count": len(df),
        "task_type": None,
        "date_column": None,
        "target_column": None,
        "evaluation_metric": None,
        "domain_flags": [],
        "problem_analysis_raw": None,
        "problem_approved": False,
        "model_approved": False,
        "frequency": None,
        "forecast_horizon": 30,
        "sequence_length": 14,
        "has_seasonality": False,
        "has_trend": False,
        "is_stationary": True,
        "lag_features_used": [],
        "rolling_features_used": [],
        "train_cutoff_date": None,
        "test_cutoff_date": None,
        "forecast_values": None,
        "forecast_dates": None,
        "profile_report": None,
        "validation_warnings": [],
        "leakage_warnings": [],
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
        "date_column": state.get("date_column"),
        "target_column": state.get("target_column"),
        "evaluation_metric": state.get("evaluation_metric"),
        "frequency": state.get("frequency"),
        "forecast_horizon": state.get("forecast_horizon"),
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
        "is_stationary": state.get("is_stationary"),
        "has_trend": state.get("has_trend"),
        "has_seasonality": state.get("has_seasonality"),
        "frequency": state.get("frequency"),
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


@router.get("/{job_id}/forecast")
async def get_forecast(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    forecast_values = state.get("forecast_values")
    if not forecast_values:
        raise HTTPException(status_code=404, detail="Forecast not yet available")

    winning = state.get("winning_experiment") or {}
    metrics = winning.get("parsed_metrics", {})

    return {
        "forecast": forecast_values,
        "forecast_dates": state.get("forecast_dates", []),
        "forecast_horizon": len(forecast_values),
        "model_type": winning.get("architecture_name", ""),
        "rmse": metrics.get("rmse", 0),
        "mae": metrics.get("mae", 0),
        "mape": metrics.get("mape", 0),
        "train_end_date": metrics.get("train_end_date", ""),
        "test_end_date": metrics.get("test_end_date", ""),
    }


@router.get("/{job_id}/history")
async def get_history(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")

    pkl_path = state.get("model_pkl_path")
    if pkl_path and os.path.exists(pkl_path):
        try:
            import pickle
            with open(pkl_path, "rb") as f:
                model_data = pickle.load(f)
            return {
                "train_dates": model_data.get("train_dates", []),
                "train_actuals": model_data.get("train_actuals", []),
                "test_dates": model_data.get("test_dates", []),
                "test_actuals": model_data.get("test_actuals", []),
                "test_predictions": model_data.get("test_predictions", []),
                "split_date": model_data.get("train_end_date", ""),
                "rmse": model_data.get("rmse", 0),
                "mae": model_data.get("mae", 0),
                "mape": model_data.get("mape", 0),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=404, detail="History not available — run the full pipeline first")


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
        "rmse": metrics.get("rmse", 0),
        "mae": metrics.get("mae", 0),
        "mape": metrics.get("mape", 0),
        "train_end_date": metrics.get("train_end_date", ""),
        "test_end_date": metrics.get("test_end_date", ""),
        "forecast_horizon": state.get("forecast_horizon", 30),
        "frequency": state.get("frequency", "daily"),
    }


@router.get("/{job_id}/model.pkl")
async def download_model_pkl(job_id: str):
    state = get_job(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    pkl_path = state.get("model_pkl_path")
    if not pkl_path or not os.path.exists(pkl_path):
        raise HTTPException(status_code=404, detail="model.pkl not available — run the full pipeline first")
    return FileResponse(pkl_path, filename="model.pkl", media_type="application/octet-stream")
