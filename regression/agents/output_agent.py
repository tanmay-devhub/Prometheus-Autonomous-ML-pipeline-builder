import base64
import json
import os
from datetime import datetime
from typing import Any, Dict

from regression.state import RegressionState
from shared.llm.router import LLMRouter
from regression.config import ARTIFACTS_DIR

SYSTEM_PROMPT = """Generate a FastAPI Python script that serves a regression ML model loaded from model.pkl.

model.pkl is a Python dict with keys: 'model', 'encoding_map', 'feature_names'.
- model: the trained sklearn/xgboost/lightgbm regressor
- encoding_map: dict containing all encoding info
- feature_names: list of post-encoding feature column names

encoding_map structure:
{{
    "target_column": str,
    "target_mapping": {{}},
    "reverse_target_mapping": {{}},
    "binary_encoders": {{col: {{"type": "binary", "mapping": {{str: int}}, "reverse": {{int: str}}}}}},
    "multi_encoders":  {{col: {{"type": "onehot", "encoded_columns": [str], "categories": [str], "col_to_category": {{str: str}}}}}},
    "num_medians": {{col: float}},
    "original_feature_columns": [str],
    "feature_columns_after_encoding": [str],
    "target_log_transformed": bool
}}

Original feature columns (before encoding): {feature_columns}
Target column: {target_column}
Model type: {model_type}
Task type: regression
MAE context: {mae_context}
R2: {r2}

Generate EXACTLY this structure — only Python code, no markdown, no backticks:

import pickle
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

app = FastAPI()
_model = None
_encoding_map = {{}}

@app.on_event("startup")
async def load_model():
    global _model, _encoding_map
    with open("model.pkl", "rb") as f:
        save = pickle.load(f)
    _model = save["model"]
    _encoding_map = save.get("encoding_map", {{}})


def _preprocess(data: dict) -> pd.DataFrame:
    orig_cols = _encoding_map.get("original_feature_columns", list(data.keys()))
    df = pd.DataFrame([{{c: data.get(c) for c in orig_cols}}])
    for col in df.columns:
        if df[col].dtype == "object":
            conv = pd.to_numeric(df[col], errors="coerce")
            if not conv.isna().all():
                df[col] = conv
    for col, enc in _encoding_map.get("binary_encoders", {{}}).items():
        if col in df.columns:
            df[col] = df[col].fillna("missing").astype(str).map(enc["mapping"]).fillna(0).astype(int)
    for col, enc in _encoding_map.get("multi_encoders", {{}}).items():
        if col in df.columns:
            col_to_cat = enc.get("col_to_category", {{}})
            col_series = df[col].apply(lambda x: float("nan") if x is None else x).fillna("nan").astype(str)
            for enc_col in enc.get("encoded_columns", []):
                category = col_to_cat.get(enc_col) if col_to_cat else enc_col[len(col) + 1:]
                df[enc_col] = (col_series == category).astype(int)
            df = df.drop(columns=[col])
    for col, med in _encoding_map.get("num_medians", {{}}).items():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(med)
    feat_cols = _encoding_map.get("feature_columns_after_encoding", [])
    if feat_cols:
        df = df.reindex(columns=feat_cols, fill_value=0)
    return df


class Item(BaseModel):
    # one Optional[Any] = None field per original feature column

@app.post("/predict")
async def predict(item: Item):
    try:
        df = _preprocess(item.model_dump())
        raw_pred = float(_model.predict(df)[0])
        if _encoding_map.get("target_log_transformed"):
            prediction = float(np.expm1(raw_pred))
        else:
            prediction = raw_pred
        return {{
            "prediction": round(prediction, 4),
            "prediction_formatted": f"{{prediction:,.2f}}",
            "mae_context": "{mae_context}",
            "model_type": "{model_type}",
            "r2": {r2}
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {{"status": "healthy", "model_type": "{model_type}", "task_type": "regression"}}

@app.get("/features")
async def features():
    orig_cols = _encoding_map.get("original_feature_columns", {feature_columns})
    return {{"required_features": orig_cols, "target_column": "{target_column}"}}

@app.get("/metrics")
async def get_metrics():
    return {{
        "model_type": "{model_type}",
        "mae_context": "{mae_context}",
        "r2": {r2}
    }}

@app.get("/encoding")
async def get_encoding():
    return {{
        "binary_features": {{col: enc["mapping"] for col, enc in _encoding_map.get("binary_encoders", {{}}).items()}},
        "onehot_features": {{col: enc["categories"] for col, enc in _encoding_map.get("multi_encoders", {{}}).items()}},
        "target_log_transformed": _encoding_map.get("target_log_transformed", False),
    }}

Return ONLY valid Python code. No markdown fences. No text before or after the code."""

REQUIREMENTS = """fastapi>=0.110.0
uvicorn>=0.29.0
pydantic>=2.0.0
scikit-learn>=1.3.0
xgboost>=2.0.0
lightgbm>=4.0.0
pandas>=2.0.0
numpy>=1.26.0
"""


def _extract_python_code(raw: str) -> str:
    raw = raw.strip()
    if "```python" in raw:
        start = raw.index("```python") + len("```python")
        end = raw.rfind("```", start)
        return raw[start:end].strip() if end > start else raw[start:].strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        return "\n".join(inner).strip()
    lines = raw.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(("import ", "from ", "class ", "def ", "@app", "#!")):
            return "\n".join(lines[i:]).strip()
    return raw


async def output_agent_node(state: RegressionState) -> RegressionState:
    router = LLMRouter()
    winning = state["winning_experiment"]
    target_column = state["target_column"]
    feature_columns = [c for c in state["dataset_columns"] if c != target_column]
    model_type = winning.get("architecture_name", "MLModel")
    metrics = winning.get("parsed_metrics", {})
    mae = metrics.get("mae", 0.0)
    r2 = metrics.get("r2", 0.0)
    target_mean = state.get("target_mean", 1.0) or 1.0
    mae_context = f"±{mae:,.2f} typical error"

    system_prompt = SYSTEM_PROMPT.format(
        feature_columns=feature_columns,
        target_column=target_column,
        model_type=model_type,
        mae_context=mae_context,
        r2=round(r2, 4),
    )

    endpoint_code = None
    for attempt in range(2):
        raw = await router.call(
            task_type="code_generation",
            system_prompt=system_prompt,
            user_message="Generate the FastAPI endpoint Python file now. Return ONLY Python code — no markdown, no prose.",
        )
        raw = _extract_python_code(raw)

        is_valid = "predict" in raw and "FastAPI" in raw and "model.pkl" in raw
        if is_valid:
            endpoint_code = raw
            break
        elif attempt == 0:
            system_prompt = (
                "The previous response was not clean Python. Return ONLY the Python source code "
                "for a FastAPI app that loads model.pkl and exposes POST /predict for regression. "
                "No markdown, no backticks, no text before or after the code."
            )

    if endpoint_code is None:
        endpoint_code = "# Code generation failed — please regenerate manually."

    state["generated_endpoint_code"] = endpoint_code
    state["generated_requirements"] = REQUIREMENTS

    winning = state.get("winning_experiment") or {}
    pkl_b64 = winning.get("model_pkl_b64")
    if pkl_b64:
        try:
            pkl_path = os.path.join(ARTIFACTS_DIR, f"{state['job_id']}_model.pkl")
            with open(pkl_path, "wb") as f:
                f.write(base64.b64decode(pkl_b64))
            state["model_pkl_path"] = pkl_path
        except Exception:
            state["model_pkl_path"] = None
    else:
        state["model_pkl_path"] = None

    state["current_phase"] = "complete"

    state["debug_log"].append({
        "phase": "output_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoint_code_length": len(endpoint_code),
    })

    return state
