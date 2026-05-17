import base64
import json
import os
from datetime import datetime
from typing import Any, Dict

from backend.state import PrometheusState
from backend.llm.router import LLMRouter
from execution.code_validator import validate_generated_code

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

SYSTEM_PROMPT = """Generate a FastAPI Python script that serves an ML model loaded from model.pkl.

model.pkl is a Python dict with keys: 'model', 'cat_encodings', 'num_medians', 'feature_names'.
- model: the trained sklearn/xgboost/lightgbm model
- cat_encodings: dict of {{col: {{value: int_index}}}} for string columns
- num_medians: dict of {{col: float}} median values for numeric columns
- feature_names: list of feature column names in training order

Feature columns: {feature_columns}
Target column: {target_column}
Model type: {model_type}
Task type: {task_type}

Generate EXACTLY this structure — only Python code, no markdown, no backticks:

import pickle
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

app = FastAPI()
_model = None
_cat_encodings = {{}}
_num_medians = {{}}
_feature_names = []

@app.on_event("startup")
async def load_model():
    global _model, _cat_encodings, _num_medians, _feature_names
    with open("model.pkl", "rb") as f:
        save = pickle.load(f)
    _model = save["model"]
    _cat_encodings = save.get("cat_encodings", {{}})
    _num_medians = save.get("num_medians", {{}})
    _feature_names = save.get("feature_names", [])

class Item(BaseModel):
    # one Optional field per feature column, default None

@app.post("/predict")
async def predict(item: Item):
    try:
        df = pd.DataFrame([item.model_dump()])
        for col, mapping in _cat_encodings.items():
            if col in df.columns:
                df[col] = df[col].fillna("missing").astype(str).map(mapping).fillna(len(mapping)).astype(int)
        for col, med in _num_medians.items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(med)
        if _feature_names:
            df = df.reindex(columns=_feature_names, fill_value=0)
        prediction = int(_model.predict(df)[0])
        probability = None
        if hasattr(_model, "predict_proba") and "{task_type}" == "binary_classification":
            probability = round(float(_model.predict_proba(df)[0][1]), 4)
        return {{"prediction": prediction, "probability": probability, "model_type": "{model_type}"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {{"status": "healthy", "model_type": "{model_type}", "task_type": "{task_type}"}}

@app.get("/features")
async def features():
    return {{"required_features": {feature_columns}, "target_column": "{target_column}"}}

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

DEPLOYMENT_README = """# Deployment Instructions

## Prerequisites
- Python 3.11+
- The `model.pkl` file (your trained model + preprocessing pipeline)

## Setup

```bash
pip install -r requirements.txt
```

Place `model.pkl` in the same directory as `endpoint.py`.

## Run the API

```bash
uvicorn endpoint:app --host 0.0.0.0 --port 8000
```

## Endpoints

- `POST /predict` — Submit feature values, receive prediction
- `GET /health` — Check API and model status
- `GET /features` — List required feature columns

## Example request

```bash
curl -X POST http://localhost:8000/predict \\
  -H "Content-Type: application/json" \\
  -d '{"feature1": 1.0, "feature2": "value"}'
```
"""


def _extract_python_code(raw: str) -> str:
    """Strip markdown fences and any prose before/after the Python code block."""
    raw = raw.strip()
    # Extract from ```python ... ``` or ``` ... ```
    if "```python" in raw:
        start = raw.index("```python") + len("```python")
        end = raw.rfind("```", start)
        return raw[start:end].strip() if end > start else raw[start:].strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        return "\n".join(inner).strip()
    # No fences — find the first line that looks like Python
    lines = raw.split("\n")
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(("import ", "from ", "class ", "def ", "@app", "#!")):
            return "\n".join(lines[i:]).strip()
    return raw


async def output_agent_node(state: PrometheusState) -> PrometheusState:
    router = LLMRouter()
    winning = state["winning_experiment"]
    target_column = state["target_column"]
    feature_columns = [c for c in state["dataset_columns"] if c != target_column]
    model_type = winning.get("architecture_name", "MLModel")
    task_type = state["task_type"]

    system_prompt = SYSTEM_PROMPT.format(
        winning_experiment_code=winning.get("generated_code", "")[:3000],
        target_column=target_column,
        feature_columns=feature_columns,
        model_type=model_type,
        task_type=task_type,
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
                "for a FastAPI app that loads model.pkl and exposes POST /predict. "
                "No markdown, no backticks, no text before or after the code."
            )

    if endpoint_code is None:
        endpoint_code = "# Code generation failed — please regenerate manually."

    state["generated_endpoint_code"] = endpoint_code
    state["generated_requirements"] = REQUIREMENTS

    # Save winning model pickle to disk so the download endpoint can serve it
    winning = state.get("winning_experiment") or {}
    pkl_b64 = winning.get("model_pkl_b64")
    if pkl_b64:
        try:
            pkl_path = os.path.join(ARTIFACTS_DIR, f"{state['job_id']}_model.pkl")
            with open(pkl_path, "wb") as f:
                f.write(base64.b64decode(pkl_b64))
            state["model_pkl_path"] = pkl_path
        except Exception as e:
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
