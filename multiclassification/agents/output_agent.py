import base64
import json
import os
from datetime import datetime
from typing import Any, Dict

from multiclassification.state import MultiClassState
from shared.llm.router import LLMRouter
from shared.execution.code_validator import validate_generated_code
from multiclassification.config import ARTIFACTS_DIR

SYSTEM_PROMPT = """Generate a FastAPI Python script that serves a multiclass classification model loaded from model.pkl.

model.pkl is a Python dict with keys: 'model', 'encoding_map', 'feature_names', 'training_metrics'.
- model: the trained sklearn/xgboost/lightgbm model
- encoding_map: dict containing all encoding info (see below)
- feature_names: list of post-encoding feature column names
- training_metrics: dict with accuracy, f1_macro, f1_weighted, per_class_f1, class_names

encoding_map structure for multiclass:
{{
    "target_column": str,
    "class_names": [str],              # e.g. ["good", "average", "poor"]
    "label_to_int": {{str: int}},       # e.g. {{"good": 2, "average": 0, "poor": 1}}
    "int_to_label": {{str: str}},       # e.g. {{"0": "average", "1": "poor", "2": "good"}}
    "binary_encoders": {{col: {{"type": "binary", "mapping": {{str: int}}}}}},
    "multi_encoders":  {{col: {{"type": "onehot", "encoded_columns": [str], "categories": [str]}}}},
    "num_medians": {{col: float}},
    "original_feature_columns": [str],
    "feature_columns_after_encoding": [str]
}}

Original feature columns (before encoding): {feature_columns}
Target column: {target_column}
Model type: {model_type}
Number of classes: {num_classes}

Generate EXACTLY this structure — only Python code, no markdown, no backticks:

import pickle
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, Dict, List

app = FastAPI()
_model = None
_encoding_map = {{}}
_training_metrics = {{}}

@app.on_event("startup")
async def load_model():
    global _model, _encoding_map, _training_metrics
    with open("model.pkl", "rb") as f:
        save = pickle.load(f)
    _model = save["model"]
    _encoding_map = save.get("encoding_map", {{}})
    _training_metrics = save.get("training_metrics", {{}})


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
        probabilities = _model.predict_proba(df)[0]
        predicted_idx = int(np.argmax(probabilities))
        int_to_label = _encoding_map.get("int_to_label", {{}})
        class_names = _encoding_map.get("class_names", [str(i) for i in range(len(probabilities))])
        prediction = int_to_label.get(str(predicted_idx), class_names[predicted_idx] if predicted_idx < len(class_names) else str(predicted_idx))
        all_probabilities = {{
            int_to_label.get(str(i), class_names[i] if i < len(class_names) else str(i)): round(float(p), 4)
            for i, p in enumerate(probabilities)
        }}
        return {{
            "prediction": prediction,
            "prediction_encoded": predicted_idx,
            "confidence": round(float(probabilities[predicted_idx]), 4),
            "all_probabilities": all_probabilities,
            "model_type": "{model_type}"
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/classes")
async def get_classes():
    class_names = _encoding_map.get("class_names", [])
    label_to_int = _encoding_map.get("label_to_int", {{}})
    return {{
        "num_classes": len(class_names),
        "class_names": class_names,
        "label_mapping": label_to_int
    }}

@app.get("/metrics")
async def get_metrics():
    return {{
        "f1_macro": _training_metrics.get("f1_macro"),
        "f1_weighted": _training_metrics.get("f1_weighted"),
        "accuracy": _training_metrics.get("accuracy"),
        "per_class_f1": _training_metrics.get("per_class_f1", {{}}),
        "num_classes": _training_metrics.get("num_classes")
    }}

@app.get("/health")
async def health():
    return {{"status": "healthy", "model_type": "{model_type}", "task_type": "multiclass_classification"}}

@app.get("/features")
async def features():
    orig_cols = _encoding_map.get("original_feature_columns", {feature_columns})
    return {{"required_features": orig_cols, "target_column": "{target_column}"}}

@app.get("/encoding")
async def get_encoding():
    return {{
        "target_column": _encoding_map.get("target_column"),
        "class_names": _encoding_map.get("class_names", []),
        "label_to_int": _encoding_map.get("label_to_int", {{}}),
        "binary_features": {{col: enc["mapping"] for col, enc in _encoding_map.get("binary_encoders", {{}}).items()}},
        "onehot_features": {{col: enc["categories"] for col, enc in _encoding_map.get("multi_encoders", {{}}).items()}},
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


async def output_agent_node(state: MultiClassState) -> MultiClassState:
    router = LLMRouter()
    winning = state["winning_experiment"]
    target_column = state["target_column"]
    feature_columns = [c for c in state["dataset_columns"] if c != target_column]
    model_type = winning.get("architecture_name", "MLModel")
    num_classes = state.get("num_classes", 0)

    system_prompt = SYSTEM_PROMPT.format(
        target_column=target_column,
        feature_columns=feature_columns,
        model_type=model_type,
        num_classes=num_classes,
    )

    endpoint_code = None
    for attempt in range(2):
        raw = await router.call(
            task_type="code_generation",
            system_prompt=system_prompt,
            user_message="Generate the FastAPI endpoint Python file now. Return ONLY Python code — no markdown, no prose.",
        )
        raw = _extract_python_code(raw)

        is_valid = "predict" in raw and "FastAPI" in raw and "model.pkl" in raw and "all_probabilities" in raw
        if is_valid:
            endpoint_code = raw
            break
        elif attempt == 0:
            system_prompt = (
                "The previous response was not clean Python. Return ONLY the Python source code "
                "for a FastAPI app that loads model.pkl and exposes POST /predict (with all_probabilities), "
                "GET /classes, GET /metrics, GET /health, GET /features. "
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
